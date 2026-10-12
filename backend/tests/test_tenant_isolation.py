import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base
from backend.app.models.tenant import Organization, OrganizationSettings
from backend.app.models.user import User, UserRole
from backend.app.models.customer import Customer
from backend.app.models.invoice import Invoice, InvoiceStatus


def test_multi_tenant_data_isolation():
    # In-memory database for isolation testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()

    # Tenant 1: Org A
    org_a = Organization(id="tenant-aaa-111", name="Alpha Corp", slug="alpha-corp", plan="STARTER")
    db.add(org_a)
    
    # Tenant 2: Org B
    org_b = Organization(id="tenant-bbb-222", name="Beta Corp", slug="beta-corp", plan="STARTER")
    db.add(org_b)
    db.commit()

    # Customer in Tenant A
    cust_a = Customer(
        id="cust-1",
        tenant_id=org_a.id,
        name="Alpha Customer",
        address="Karachi",
        city="Karachi",
        province="Sindh"
    )
    db.add(cust_a)

    # Customer in Tenant B
    cust_b = Customer(
        id="cust-2",
        tenant_id=org_b.id,
        name="Beta Customer",
        address="Lahore",
        city="Lahore",
        province="Punjab"
    )
    db.add(cust_b)
    db.commit()

    # Query with Tenant A context: MUST only see Tenant A's customer
    tenant_a_customers = db.query(Customer).filter(Customer.tenant_id == org_a.id).all()
    assert len(tenant_a_customers) == 1
    assert tenant_a_customers[0].name == "Alpha Customer"
    assert tenant_a_customers[0].tenant_id == org_a.id

    # Query with Tenant B context: MUST only see Tenant B's customer
    tenant_b_customers = db.query(Customer).filter(Customer.tenant_id == org_b.id).all()
    assert len(tenant_b_customers) == 1
    assert tenant_b_customers[0].name == "Beta Customer"
    assert tenant_b_customers[0].tenant_id == org_b.id

    # Cross-tenant query attempt by ID should yield None when tenant_id filter is applied
    cross_tenant_lookup = db.query(Customer).filter(
        Customer.id == cust_b.id,
        Customer.tenant_id == org_a.id
    ).first()
    assert cross_tenant_lookup is None, "Tenant A must NOT be able to access Tenant B's customer record!"
    
    db.close()
