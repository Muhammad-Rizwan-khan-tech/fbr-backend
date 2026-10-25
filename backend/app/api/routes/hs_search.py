from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_tenant
from backend.app.models.tenant import Organization
from backend.app.services.hs_catalog_search import search_catalog

router = APIRouter(prefix='/reference', tags=['HS Code Search'])

@router.get('/hs-codes')
def search_hs_codes(
    search: str = Query('', max_length=120),
    q: str = Query('', max_length=120),
    limit: int = Query(25, ge=1, le=100),
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    term = (q or search).strip()
    if term and len(term) < 2:
        return []
    return search_catalog(db, tenant.id, term, limit)
