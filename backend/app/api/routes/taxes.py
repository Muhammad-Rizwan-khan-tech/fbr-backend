from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user
from backend.app.models.user import User
from backend.app.models.reference import HSCode, UOM, TaxRate, SaleType, TaxProfile
from backend.app.schemas.reference import (
    HSCodeResponse, UOMResponse, TaxRateResponse, SaleTypeResponse, TaxProfileResponse
)

router = APIRouter(prefix="/tax", tags=["Tax Reference Data"])


@router.get("/hs-codes", response_model=List[HSCodeResponse])
def get_hs_codes(
    search: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(HSCode).filter(HSCode.is_active == True)
    if search:
        s = f"%{search}%"
        query = query.filter((HSCode.code.ilike(s)) | (HSCode.description.ilike(s)))
    return query.limit(limit).all()


@router.get("/uoms", response_model=List[UOMResponse])
def get_uoms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(UOM).filter(UOM.is_active == True).all()


@router.get("/rates", response_model=List[TaxRateResponse])
def get_tax_rates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(TaxRate).filter(TaxRate.is_active == True).all()


@router.get("/sale-types", response_model=List[SaleTypeResponse])
def get_sale_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(SaleType).filter(SaleType.is_active == True).all()


@router.get("/profiles", response_model=List[TaxProfileResponse])
def get_tax_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(TaxProfile).filter(TaxProfile.is_active == True).all()
