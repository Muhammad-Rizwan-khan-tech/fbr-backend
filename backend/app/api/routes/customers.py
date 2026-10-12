from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant
from backend.app.models.user import User
from backend.app.models.tenant import Organization
from backend.app.models.customer import Customer
from backend.app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=List[CustomerResponse])
def list_customers(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    query = db.query(Customer).filter(Customer.tenant_id == tenant.id)
    if is_active is not None:
        query = query.filter(Customer.is_active == is_active)
    if search:
        s = f"%{search}%"
        query = query.filter((Customer.name.ilike(s)) | (Customer.ntn.ilike(s)) | (Customer.strn.ilike(s)))
    return query.order_by(Customer.name).all()


@router.post("", response_model=CustomerResponse)
def create_customer(
    data: CustomerCreate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    customer = Customer(
        tenant_id=tenant.id,
        created_by=current_user.id,
        name=data.name,
        ntn=data.ntn,
        strn=data.strn,
        cnic=data.cnic,
        registration_type=data.registration_type,
        buyer_type=data.buyer_type,
        address=data.address,
        city=data.city,
        province=data.province,
        postal_code=data.postal_code,
        country=data.country,
        phone=data.phone,
        email=data.email,
        buyer_reference=data.buyer_reference,
        is_active=data.is_active
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="CREATE_CUSTOMER",
        entity="Customer",
        entity_id=customer.id,
        user_id=current_user.id,
        user_email=current_user.email,
        after_state={"name": customer.name, "ntn": customer.ntn}
    )

    return customer


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: str,
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    cust = db.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == tenant.id).first()
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    return cust


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cust = db.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == tenant.id).first()
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")

    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(cust, field, val)

    cust.updated_by = current_user.id
    db.commit()
    db.refresh(cust)

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="UPDATE_CUSTOMER",
        entity="Customer",
        entity_id=cust.id,
        user_id=current_user.id,
        user_email=current_user.email,
        after_state=data.model_dump(exclude_unset=True)
    )

    return cust
