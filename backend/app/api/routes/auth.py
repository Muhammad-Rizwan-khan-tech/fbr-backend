from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import re

from backend.app.core.database import get_db
from backend.app.core.security import verify_password, get_password_hash, create_access_token
from backend.app.core.dependencies import get_current_user
from backend.app.models.tenant import Organization, OrganizationSettings, Subscription, SubscriptionUsage
from backend.app.models.taxpayer import Taxpayer
from backend.app.models.branch import Branch
from backend.app.models.user import User, UserRole
from backend.app.schemas.auth import UserLogin, UserRegister, Token, UserResponse
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token)
def register(data: UserRegister, db: Session = Depends(get_db)):
    # Check if user email already exists
    existing_user = db.query(User).filter(User.email == data.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    # Generate slug for organization
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", data.org_name.strip().lower()).strip("-")
    slug_candidate = slug
    counter = 1
    while db.query(Organization).filter(Organization.slug == slug_candidate).first():
        slug_candidate = f"{slug}-{counter}"
        counter += 1

    # 1. Create Organization
    org = Organization(
        name=data.org_name,
        slug=slug_candidate,
        plan="STARTER",
        status="ACTIVE"
    )
    db.add(org)
    db.flush()

    # 2. Create Default Organization Settings
    settings = OrganizationSettings(
        organization_id=org.id,
        invoice_prefix="INV",
        next_invoice_number=1001,
        fbr_mode="DEMO"
    )
    db.add(settings)

    # 3. Create Default Taxpayer Profile
    taxpayer = Taxpayer(
        tenant_id=org.id,
        legal_name=data.org_name,
        ntn=data.ntn or "7654321-0",
        strn="3277876123456",
        registration_type="REGISTERED",
        business_type="WHOLESALER",
        address="Suite 401, Business Center, Shahrah-e-Faisal",
        city="Karachi",
        province="Sindh",
        country="Pakistan",
        phone=data.phone,
        email=data.email
    )
    db.add(taxpayer)

    # 4. Create Main Branch
    main_branch = Branch(
        tenant_id=org.id,
        branch_name="Head Office",
        branch_code="KHI-01",
        fbr_pos_id="POS-1001",
        address="Suite 401, Business Center, Shahrah-e-Faisal",
        city="Karachi",
        province="Sindh",
        phone=data.phone,
        email=data.email,
        is_main=True
    )
    db.add(main_branch)

    # 5. Create Organization Admin User
    user = User(
        tenant_id=org.id,
        email=data.email.lower(),
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=UserRole.ORG_ADMIN.value,
        phone=data.phone
    )
    db.add(user)

    # 6. Create Initial Subscription
    sub = Subscription(
        organization_id=org.id,
        plan="STARTER",
        status="ACTIVE",
        monthly_invoice_limit=100
    )
    db.add(sub)

    db.commit()
    db.refresh(user)
    db.refresh(org)

    AuditService.log(
        db=db,
        tenant_id=org.id,
        action="TENANT_REGISTER",
        entity="Organization",
        entity_id=org.id,
        user_id=user.id,
        user_email=user.email,
        after_state={"org_name": org.name, "admin_email": user.email}
    )

    access_token = create_access_token(
        subject=user.id,
        tenant_id=org.id,
        role=user.role
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        tenant_id=org.id,
        user_name=user.full_name,
        org_name=org.name
    )


@router.post("/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated")

    org = db.query(Organization).filter(Organization.id == user.tenant_id).first()
    if not org or not org.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization is inactive")

    access_token = create_access_token(
        subject=user.id,
        tenant_id=user.tenant_id,
        role=user.role
    )

    AuditService.log(
        db=db,
        tenant_id=user.tenant_id,
        action="USER_LOGIN",
        entity="User",
        entity_id=user.id,
        user_id=user.id,
        user_email=user.email
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        tenant_id=user.tenant_id,
        user_name=user.full_name,
        org_name=org.name
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
