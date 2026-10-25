from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant
from backend.app.models.user import User
from backend.app.models.tenant import Organization
from backend.app.models.product import Product
from backend.app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=List[ProductResponse])
def list_products(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    query = db.query(Product).filter(Product.tenant_id == tenant.id)
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
    if search:
        s = f"%{search}%"
        query = query.filter((Product.name.ilike(s)) | (Product.item_code.ilike(s)) | (Product.hs_code.ilike(s)))
    return query.order_by(Product.name).all()


@router.post("", response_model=ProductResponse)
def create_product(
    data: ProductCreate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from backend.app.services.master_management import validate_changes
    clean = validate_changes(data.model_dump(), ['item_code','name','hs_code','uom','sale_type','tax_rate','unit_price','is_active'], 'Product')
    data = ProductCreate(**clean)
    # Check duplicate item code in tenant
    existing = db.query(Product).filter(
        Product.tenant_id == tenant.id,
        Product.item_code == data.item_code.upper()
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Product with this item code already exists")

    product = Product(
        tenant_id=tenant.id,
        created_by=current_user.id,
        item_code=data.item_code.upper(),
        name=data.name,
        description=data.description,
        hs_code=data.hs_code,
        uom=data.uom,
        sale_type=data.sale_type,
        tax_rate=data.tax_rate,
        sro_reference=data.sro_reference,
        unit_price=data.unit_price,
        is_active=data.is_active
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="CREATE_PRODUCT",
        entity="Product",
        entity_id=product.id,
        user_id=current_user.id,
        user_email=current_user.email,
        after_state={"item_code": product.item_code, "name": product.name, "tax_rate": str(product.tax_rate)}
    )

    return product


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: str,
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    prod = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant.id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    return prod


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    data: ProductUpdate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    prod = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant.id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    changes = data.model_dump(exclude_unset=True)
    from backend.app.services.master_management import validate_changes
    changes = validate_changes(changes, ['item_code', 'name', 'hs_code', 'uom', 'sale_type', 'tax_rate', 'unit_price', 'is_active'], 'Product')
    before = {field: getattr(prod, field) for field in changes}
    if "item_code" in changes:
        duplicate = db.query(Product.id).filter(Product.tenant_id == tenant.id, Product.item_code == changes['item_code'], Product.id != product_id).first()
        if duplicate:
            raise HTTPException(409, "Product with this item code already exists")
    for field, val in changes.items():
        if field == "item_code" and val:
            val = val.upper()
        setattr(prod, field, val)

    prod.updated_by = current_user.id
    AuditService.log(db=db, tenant_id=tenant.id, action="UPDATE_PRODUCT", entity="Product", entity_id=prod.id, user_id=current_user.id, user_email=current_user.email, before_state=before, after_state=changes, commit=False)
    db.commit()
    db.refresh(prod)
    return prod


@router.delete("/{product_id}")
def delete_product(product_id: str, tenant: Organization = Depends(get_current_tenant), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from backend.app.services.master_management import remove_master
    return remove_master(db, tenant.id, product_id, Product, current_user)
