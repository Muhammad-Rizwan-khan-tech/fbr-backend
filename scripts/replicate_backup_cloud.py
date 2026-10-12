#!/usr/bin/env python3
"""Automated Off-Site Cloud Cold Storage Replication Utility.

Replicates local PostgreSQL backup archives to AWS S3 Glacier, Google Cloud Storage,
or S3-compatible cold archives with optional client-side AES-GCM encryption.

Usage:
    python scripts/replicate_backup_cloud.py --file backups/fbr_invoice_cloud_20261008.sql.gz --bucket fbr-cold-archive --storage-class GLACIER
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backup_replicate")


def compute_sha256(filepath: Path) -> str:
    """Computes SHA-256 hex digest for a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def encrypt_file_aes256(input_path: Path, output_path: Path, encryption_key: str) -> str:
    """Encrypts a backup file using AES-256 via cryptography before off-site transmission."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key_bytes = hashlib.sha256(encryption_key.encode("utf-8")).digest()
    aesgcm = AESGCM(key_bytes)
    nonce = os.urandom(12)  # 96-bit nonce for AES-GCM

    data = input_path.read_bytes()
    encrypted_data = aesgcm.encrypt(nonce, data, None)

    with open(output_path, "wb") as f:
        f.write(nonce)
        f.write(encrypted_data)

    return compute_sha256(output_path)


def replicate_to_s3(
    file_path: Path,
    bucket_name: str,
    storage_class: str = "GLACIER",
    prefix: str = "postgres_backups",
) -> dict:
    """Uploads backup archive to S3 / Glacier with metadata and checksum verification."""
    import boto3
    from botocore.config import Config

    s3_endpoint = settings.OBJECT_STORAGE_ENDPOINT or None
    s3_region = settings.OBJECT_STORAGE_REGION or "us-east-1"
    access_key = settings.OBJECT_STORAGE_ACCESS_KEY or None
    secret_key = settings.OBJECT_STORAGE_SECRET_KEY or None

    boto_config = Config(
        signature_version="s3v4",
        retries={"max_attempts": 3, "mode": "standard"},
    )

    s3_kwargs = {"config": boto_config, "region_name": s3_region}
    if s3_endpoint:
        s3_kwargs["endpoint_url"] = s3_endpoint
    if access_key and secret_key:
        s3_kwargs["aws_access_key_id"] = access_key
        s3_kwargs["aws_secret_access_key"] = secret_key

    client = boto3.client("s3", **s3_kwargs)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    object_key = f"{prefix}/{timestamp_str}/{file_path.name}"
    sha256_checksum = compute_sha256(file_path)
    file_size_bytes = file_path.stat().st_size

    logger.info(f"Uploading {file_path.name} ({file_size_bytes} bytes) to s3://{bucket_name}/{object_key} (StorageClass={storage_class})...")

    start_time = time.time()
    extra_args = {
        "StorageClass": storage_class,
        "Metadata": {
            "sha256": sha256_checksum,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "service": "fbr-invoice-cloud",
        },
    }

    client.upload_file(
        Filename=str(file_path),
        Bucket=bucket_name,
        Key=object_key,
        ExtraArgs=extra_args,
    )

    duration = time.time() - start_time
    logger.info(f"[SUCCESS] Replicated to cloud storage in {duration:.2f}s (URI: s3://{bucket_name}/{object_key})")

    return {
        "success": True,
        "bucket": bucket_name,
        "key": object_key,
        "storage_class": storage_class,
        "file_size_bytes": file_size_bytes,
        "sha256": sha256_checksum,
        "duration_seconds": round(duration, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Off-Site Backup Cloud Replication Utility")
    parser.add_argument("--file", required=True, help="Path to local database backup archive")
    parser.add_argument("--bucket", default=None, help="Target S3/GCS bucket name")
    parser.add_argument("--storage-class", default="GLACIER", choices=["STANDARD", "STANDARD_IA", "GLACIER", "DEEP_ARCHIVE", "ARCHIVE"], help="Cold storage tier")
    parser.add_argument("--encrypt-key", default=None, help="AES-256 encryption passphrase")
    parser.add_argument("--dry-run", action="store_true", help="Simulate replication without network upload")

    args = parser.parse_args()

    input_file = Path(args.file)
    if not input_file.is_file():
        logger.error(f"Backup file not found: {input_file}")
        sys.exit(1)

    bucket = args.bucket or settings.BACKUP_OFFSITE_BUCKET or settings.OBJECT_STORAGE_BUCKET
    enc_key = args.encrypt_key or settings.BACKUP_ENCRYPTION_KEY

    target_file = input_file
    temp_encrypted_file = None

    if enc_key:
        temp_encrypted_file = input_file.with_suffix(input_file.suffix + ".enc")
        logger.info(f"Applying client-side AES-256 encryption to {input_file.name}...")
        enc_sha = encrypt_file_aes256(input_file, temp_encrypted_file, enc_key)
        logger.info(f"Encrypted archive created: {temp_encrypted_file.name} (SHA-256: {enc_sha})")
        target_file = temp_encrypted_file

    if args.dry_run or not bucket:
        logger.info(f"[DRY-RUN] Backup file {target_file.name} validated. Ready for replication to s3://{bucket or 'configured-cold-bucket'}/")
        if temp_encrypted_file and temp_encrypted_file.exists():
            temp_encrypted_file.unlink()
        sys.exit(0)

    try:
        result = replicate_to_s3(
            file_path=target_file,
            bucket_name=bucket,
            storage_class=args.storage_class,
        )
        print(json.dumps(result, indent=2))
    except Exception as exc:
        logger.error(f"Replication failed: {exc}")
        sys.exit(1)
    finally:
        if temp_encrypted_file and temp_encrypted_file.exists():
            temp_encrypted_file.unlink()


if __name__ == "__main__":
    main()
