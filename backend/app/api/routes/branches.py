from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant, require_roles
from backend.app.models.user import User, UserRole
from backend.app.models.tenant import Organization
from backend.app.models.branch import Branch
from backend.app.schemas.tenant import BranchCreate, BranchUpdate, BranchResponse
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/branches", tags=["Branches"])


@router.get("", response_model=List[BranchResponse])
def list_branches(
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    return db.query(Branch).filter(Branch.tenant_id == tenant.id).all()


@router.post("", response_model=BranchResponse)
def create_branch(
    data: BranchCreate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_roles(UserRole.ORG_ADMIN.value)),
    db: Session = Depends(get_db)
):
    # Check if branch code exists in tenant
    existing = db.query(Branch).filter(
        Branch.tenant_id == tenant.id,
        Branch.branch_code == data.branch_code.upper()
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Branch with this code already exists")

    branch = Branch(
        tenant_id=tenant.id,
        branch_name=data.branch_name,
        branch_code=data.branch_code.upper(),
        fbr_pos_id=data.fbr_pos_id,
        address=data.address,
        city=data.city,
        province=data.province,
        phone=data.phone,
        email=data.email,
        is_active=data.is_active,
        is_main=data.is_main
    )
    db.add(branch)
    db.commit()
    db.refresh(branch)

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="CREATE_BRANCH",
        entity="Branch",
        entity_id=branch.id,
        user_id=current_user.id,
        user_email=current_user.email,
        after_state={"branch_code": branch.branch_code, "branch_name": branch.branch_name}
    )

    return branch


@router.patch("/{branch_id}", response_model=BranchResponse)
def update_branch(
    branch_id: str,
    data: BranchUpdate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_roles(UserRole.ORG_ADMIN.value)),
    db: Session = Depends(get_db)
):
    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.tenant_id == tenant.id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    for field, val in data.model_dump(exclude_unset=True).items():
        if field == "branch_code" and val:
            val = val.upper()
        setattr(branch, field, val)

    db.commit()
    db.refresh(branch)
    return branch
