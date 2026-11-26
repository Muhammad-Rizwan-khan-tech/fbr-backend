"""Temporary, environment-gated PostgreSQL cutover. No HTTP migration surface."""
import hashlib
import io
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import threading
import time
from urllib.request import urlopen

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict


BACKUP_SCHEMA = "before_transfer_20261126"
PACKAGES = {
    "postgresql-client-18_18.7-1.pgdg12%2B5_amd64.deb":
        "196d499b4e965fe379bf7a51c7515c39e3553e839258b335d0ee6859e90742bb",
}


def _dsn(raw):
    return re.sub(r"^postgresql\+psycopg(?:2)?://", "postgresql://", raw)


def _environment(dsn):
    cfg = conninfo_to_dict(_dsn(dsn))
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("PG"):
            env.pop(key)
    for key, value in cfg.items():
        name = {"dbname": "PGDATABASE", "connect_timeout": "PGCONNECT_TIMEOUT", "application_name": "PGAPPNAME"}.get(key, "PG" + key.upper())
        env[name] = value
    env["PGCONNECT_TIMEOUT"] = "20"
    env["PGOPTIONS"] = "-c timezone=UTC -c extra_float_digits=3"
    return env


def _clients(root):
    for filename, digest in PACKAGES.items():
        with urlopen("https://apt.postgresql.org/pub/repos/apt/pool/main/p/postgresql-18/" + filename, timeout=60) as response:
            blob = response.read()
        if hashlib.sha256(blob).hexdigest() != digest:
            raise RuntimeError("PostgreSQL client checksum mismatch")
        # Debian ar container; unpack only its data archive using safe extraction.
        if blob[:8] != b"!<arch>\n":
            raise RuntimeError("Invalid PostgreSQL client package")
        offset = 8
        while offset + 60 <= len(blob):
            header = blob[offset:offset + 60]
            size = int(header[48:58])
            name = header[:16].decode().strip().rstrip("/")
            data = blob[offset + 60:offset + 60 + size]
            if name.startswith("data.tar"):
                with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                    archive.extractall(root, filter="data")
                break
            offset += 60 + size + size % 2
        else:
            raise RuntimeError("Missing PostgreSQL client archive")
    import psycopg_binary
    bundled = Path(psycopg_binary.__file__).resolve().parent.parent / "psycopg_binary.libs"
    pq = next(bundled.glob("libpq-*.so*"))
    lib = root / "pq"
    lib.mkdir()
    (lib / "libpq.so.5").symlink_to(pq)
    return root / "usr/lib/postgresql/18/bin", str(lib) + ":" + str(bundled)


def _run(binary, args, env):
    result = subprocess.run([str(binary), *args], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    if result.returncode:
        first_line = result.stderr.decode(errors="replace").splitlines()[:1]
        diagnostic = first_line[0] if first_line else "no client diagnostic"
        diagnostic = re.sub(r"postgres(?:ql)?://\S+", "[redacted URL]", diagnostic)
        for key, value in env.items():
            if "PASSWORD" in key and value:
                diagnostic = diagnostic.replace(value, "[redacted]")
        print("FBR_TRANSFER_CLIENT_DIAGNOSTIC " + diagnostic[:300], flush=True)
        # Never log SQL, row contents, credentials or raw connection errors.
        raise RuntimeError("PostgreSQL " + binary.name + " failed (exit " + str(result.returncode) + ")")
    return result.stdout.decode()


def _signature(conn, table):
    return conn.execute(sql.SQL("SELECT count(*), md5(coalesce(string_agg(h, '' ORDER BY h), '')) FROM (SELECT md5(row_to_json(t)::text) AS h FROM public.{} t) s").format(sql.Identifier(table))).fetchone()


def run_transfer_if_requested():
    source_url = os.environ.get("FBR_MIGRATION_SOURCE_URL", "")
    if not source_url:
        return
    target_url = os.environ.get("DATABASE_URL", "")
    source_cfg = conninfo_to_dict(_dsn(source_url))
    target_cfg = conninfo_to_dict(_dsn(target_url))
    if source_cfg.get("host") != "dpg-dbdop6l9fdbs7384ugvg-a":
        raise RuntimeError("Unexpected migration source")
    if target_cfg.get("host") != "dpg-dc45nd4ipgvc738n8keg-a.ohio-postgres.render.com":
        raise RuntimeError("Unexpected migration destination")
    src = None
    stage = "destination-check"
    try:
        with psycopg.connect(_dsn(target_url), connect_timeout=20, autocommit=True) as dst:
            dst.execute("SELECT pg_advisory_lock(20261126, 4711)")
            if dst.execute("SELECT to_regclass('fbr_transfer_meta.completed')").fetchone()[0]:
                if dst.execute("SELECT count(*) FROM fbr_transfer_meta.completed WHERE source_database='fbr_cloud'").fetchone()[0] == 1:
                    print("FBR_DATABASE_TRANSFER_ALREADY_COMPLETE", flush=True)
                    return
                raise RuntimeError("Unexpected migration marker")
            if dst.execute("SELECT count(*) FROM pg_namespace WHERE nspname=%s", (BACKUP_SCHEMA,)).fetchone()[0]:
                raise RuntimeError("Destination backup already exists without completion marker")
            # Destination must not be serving any application during the restore.
            if dst.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND application_name NOT LIKE 'render%' AND state<>'idle'").fetchone()[0]:
                raise RuntimeError("Destination has active transactions")
            with tempfile.TemporaryDirectory(prefix="fbr-transfer-") as directory:
                root = Path(directory)
                stage = "download-clients"
                bins, libs = _clients(root)
                src_env, dst_env = _environment(source_url), _environment(target_url)
                src_env["LD_LIBRARY_PATH"] = dst_env["LD_LIBRARY_PATH"] = libs
                stage = "source-snapshot"
                src = psycopg.connect(_dsn(source_url), connect_timeout=20)
                src.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                src.execute("SET LOCAL timezone='UTC'")
                src.execute("SET LOCAL extra_float_digits=3")
                src.execute("SET LOCAL lock_timeout='45s'")
                tables = [row[0] for row in src.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
                if len(tables) != 38:
                    raise RuntimeError("Unexpected source table set")
                src.execute(sql.SQL("LOCK TABLE {} IN SHARE MODE").format(sql.SQL(", ").join(sql.Identifier("public", name) for name in tables)))
                if src.execute("SELECT count(*) FROM invoice_submission_jobs WHERE status IN ('QUEUED','PROCESSING','RETRY_WAIT')").fetchone()[0]:
                    raise RuntimeError("Source has pending invoice jobs")
                snapshot = src.execute("SELECT pg_export_snapshot()").fetchone()[0]
                signatures = {name: _signature(src, name) for name in tables}
                dump = root / "source.dump"
                stage = "dump-source"
                _run(bins / "pg_dump", ["--format=custom", "--schema=public", "--no-owner", "--no-acl", "--snapshot=" + snapshot, "--file=" + str(dump)], src_env)
                toc = _run(bins / "pg_restore", ["--list", str(dump)], dst_env)
                restored_sql = root / "restore.sql"
                _run(bins / "pg_restore", ["--no-owner", "--no-acl", "--file=" + str(restored_sql), str(dump)], dst_env)
                script = root / "transaction.sql"
                with script.open("w") as out:
                    out.write("BEGIN;\nSET LOCAL timezone='UTC';\nSET LOCAL extra_float_digits=3;\n")
                    out.write("ALTER SCHEMA public RENAME TO " + BACKUP_SCHEMA + ";\n")
                    if not re.search(r" SCHEMA - public ", toc):
                        out.write("CREATE SCHEMA public;\n")
                    out.write(restored_sql.read_text())
                    for name, (count, digest) in signatures.items():
                        # Identifiers originate from the locked PostgreSQL catalog.
                        ident = '"' + name.replace('"', '""') + '"'
                        out.write("\nDO $verify$ DECLARE c bigint; d text; BEGIN SELECT count(*), md5(coalesce(string_agg(h, '' ORDER BY h), '')) INTO c,d FROM (SELECT md5(row_to_json(t)::text) h FROM public." + ident + " t) s; IF c <> " + str(count) + " OR d <> '" + digest + "' THEN RAISE EXCEPTION 'Migration row verification failed'; END IF; END $verify$;\n")
                    out.write("CREATE SCHEMA fbr_transfer_meta; CREATE TABLE fbr_transfer_meta.completed(source_database text PRIMARY KEY, completed_at timestamptz NOT NULL DEFAULT now(), table_count integer NOT NULL, row_count bigint NOT NULL, backup_schema text NOT NULL);\n")
                    out.write("INSERT INTO fbr_transfer_meta.completed(source_database,table_count,row_count,backup_schema) VALUES ('fbr_cloud',38," + str(sum(v[0] for v in signatures.values())) + ",'" + BACKUP_SCHEMA + "');\nCOMMIT;\n")
                stage = "transactional-restore"
                _run(bins / "psql", ["-X", "-v", "ON_ERROR_STOP=1", "--file=" + str(script)], dst_env)
                print("FBR_DATABASE_TRANSFER_COMPLETE tables=38 rows=" + str(sum(v[0] for v in signatures.values())) + " backup_schema=" + BACKUP_SCHEMA, flush=True)
                # Keep writes blocked until Render has routed traffic to this instance
                # and terminated its predecessor; only locks, never source data writes.
                locked_source = src
                def release():
                    time.sleep(180)
                    locked_source.rollback()
                    locked_source.close()
                threading.Thread(target=release, daemon=True).start()
                src = None
    except Exception as error:
        print("FBR_DATABASE_TRANSFER_FAILED stage=" + stage + " type=" + type(error).__name__, flush=True)
        raise RuntimeError("Database transfer failed safely; do not retry without inspection") from None
    finally:
        if src is not None:
            src.rollback()
            src.close()
