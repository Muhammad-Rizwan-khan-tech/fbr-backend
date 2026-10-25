from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_tenant
from backend.app.models.tenant import Organization
from backend.app.models.reference import HSCode
from backend.app.core.fbr_hs_code import normalize_hs_code
from backend.app.services.pral_reference_service import pral_reference_service

router=APIRouter(prefix='/reference',tags=['HS Code Search'])

@router.get('/hs-codes')
async def search_hs_codes(search: str = Query('',max_length=120), q: str = Query('',max_length=120), limit: int = Query(25,ge=1,le=100), tenant: Organization = Depends(get_current_tenant), db: Session = Depends(get_db)):
    term=(q or search).strip()
    if term and len(term)<2: return []
    query=db.query(HSCode).filter(HSCode.is_active.is_(True))
    if term:
        literal=term.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        digits=literal.replace('.','')
        query=query.filter(or_(HSCode.code.ilike(literal+'%',escape='\\'), func.replace(HSCode.code,'.','').ilike(digits+'%',escape='\\'),HSCode.description.ilike('%'+literal+'%',escape='\\')))
    records=query.order_by(HSCode.code).limit(limit).all()
    result={normalize_hs_code(row.code):{'hs_code':normalize_hs_code(row.code),'description':row.description,'chapter':row.chapter or row.code[:2],'default_uom':None,'default_rate':None,'sale_type':None,'source':'LOCAL_CATALOG','official_live_verified':False} for row in records}
    # Reuse tenant-authorized official catalog/cache. Failure preserves local suggestions.
    # Rates/UoM depend on sale type/province/date; an HS code alone cannot determine 18%.
    try:
        env=await pral_reference_service.fetch_item_codes_envelope(search=None if term.replace('.','').isdigit() else term,limit=0 if term.replace('.','').isdigit() else limit,db=db,tenant_id=tenant.id)
        for row in env.data or []:
            code=normalize_hs_code(row.get('hs_code') or row.get('hS_CODE'))
            desc=str(row.get('description') or '')
            if term and not (term.lower() in desc.lower() or term.replace('.','') in code.replace('.','')): continue
            result[code]={'hs_code':code,'description':desc,'chapter':code[:2],'default_uom':None,'default_rate':None,'sale_type':None,'source':env.source,'official_live_verified':env.official_live_verified,'stale':env.stale}
            if len(result)>=limit: break
    except Exception:
        pass
    return list(result.values())[:limit]
