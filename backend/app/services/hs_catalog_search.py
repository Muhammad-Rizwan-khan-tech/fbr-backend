"""Search public tariff dictionaries locally; keystrokes never call PRAL."""
import gzip
import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from sqlalchemy import or_
from backend.app.core.fbr_hs_code import normalize_hs_code
from backend.app.models.pral_catalog import FBRReferenceCatalog
from backend.app.models.reference import HSCode

COMMON_CODES = ('8504.4010', '8528.5200', '8528.5900', '8471.3010', '8517.1300', '3004.9099', '4811.9000')

@lru_cache(maxsize=8)
def parse_catalog(payload):
    raw = json.loads(payload)
    rows = raw.get('items', []) if isinstance(raw, dict) else raw
    result = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        raw_code = row.get('hs_code') or row.get('hS_CODE') or ''
        if len(re.sub(r'\D', '', str(raw_code))) != 8 or not row.get('description'):
            continue
        code = normalize_hs_code(raw_code)
        result[code] = {'hs_code': code, 'description': str(row['description'])}
    return result

@lru_cache(maxsize=1)
def bundled_catalog():
    path = Path(__file__).resolve().parents[1] / 'assets' / 'hs_codes_snapshot.json.gz'
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        payload = stream.read()
    return parse_catalog(payload)

def search_catalog(db, tenant_id, term, limit):
    catalog = {code: dict(row, source='OFFICIAL_SNAPSHOT', official_live_verified=False, stale=True, as_of='2026-10-25') for code, row in bundled_catalog().items()}
    cached = db.query(FBRReferenceCatalog).filter(
        FBRReferenceCatalog.catalog_key == 'itemdesccode',
        FBRReferenceCatalog.source.in_(('PRAL_LIVE', 'OFFICIAL_IMPORT', 'CACHED_OFFICIAL')),
        or_(FBRReferenceCatalog.tenant_id == tenant_id, FBRReferenceCatalog.tenant_id.is_(None)),
    ).order_by(FBRReferenceCatalog.fetched_at.desc()).limit(2).all()
    for entry in reversed(cached):
        try:
            expires = entry.expires_at
            if expires and expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            stale = not expires or expires <= datetime.now(timezone.utc)
            for code, row in parse_catalog(entry.payload).items():
                catalog[code] = dict(row, source='CACHED_OFFICIAL', origin_source=entry.source, official_live_verified=False, stale=stale, as_of=entry.fetched_at.isoformat())
        except (ValueError, TypeError):
            continue
    for entry in db.query(HSCode).filter(HSCode.is_active.is_(True)).all():
        try:
            code = normalize_hs_code(entry.code)
            catalog.setdefault(code, {'hs_code': code, 'description': entry.description, 'source': 'LOCAL_CATALOG', 'official_live_verified': False, 'stale': False})
        except ValueError:
            continue
    query = term.strip().casefold()
    numeric = re.sub(r'[.\s]', '', query)
    tokens = query.split()
    matches = [row for code, row in catalog.items() if not query or (code.replace('.', '').startswith(numeric) if numeric.isdigit() else all(token in row['description'].casefold() for token in tokens))]
    def rank(row):
        code = row['hs_code']
        return (0 if code.replace('.', '') == numeric else 1, COMMON_CODES.index(code) if code in COMMON_CODES else len(COMMON_CODES), code)
    matches.sort(key=rank)
    return [dict(row, chapter=row['hs_code'][:2], default_uom=None, default_rate=None, sale_type=None) for row in matches[:limit]]
