from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal, Base, engine
from backend.app.core.security import get_password_hash
from backend.app.models.tenant import Organization, OrganizationSettings, Subscription, SubscriptionUsage
from backend.app.models.user import User, UserRole
from backend.app.models.taxpayer import Taxpayer
from backend.app.models.branch import Branch
from backend.app.models.reference import HSCode, UOM, TaxRate, SaleType, TaxProfile
from backend.app.models.customer import Customer
from backend.app.models.product import Product
from backend.app.models.invoice import Invoice, InvoiceItem, InvoiceStatus, FBRSubmissionStatus
from backend.app.models.note import CreditNote, DebitNote, NoteStatus
from backend.app.models.license import License, LicenseStatus, ActivationKey, ActivationKeyStatus
from backend.app.models.fbr_credential import FBRCredential, FBRConnectionStatus
from backend.app.models.fbr import FBRSubmission, FBRSubmissionAttempt
from backend.app.core.crypto import hash_activation_secret
from backend.app.services.tax_engine import PakistanTaxEngine


def seed_database(db: Session = None):
    close_after = False
    if db is None:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        close_after = True

    try:
        # Check if already seeded
        if db.query(Organization).filter(Organization.slug == "abc-distribution").first():
            print("Database already contains demo organization. Skipping seed.")
            return

        print("Seeding FBR Reference Data...")
        # 1. HS Codes
        hs_data = [
            ("8471.30.10", "Portable automatic data processing machines, weighing not more than 10 kg"),
            ("8471.60.20", "Input or output units, whether or not containing storage units in the same housing"),
            ("4811.90.00", "Paper, paperboard, cellulose wadding and webs of cellulose fibres, coated/impregnated"),
            ("8303.00.00", "Armoured or reinforced safes, strong-boxes and doors and safe deposit lockers for strong-rooms, cash or deed boxes"),
            ("8517.13.00", "Smartphones for cellular networks or for other wireless networks"),
            ("3004.90.99", "Medicaments consisting of mixed or unmixed products for therapeutic or prophylactic uses"),
            ("5208.11.00", "Woven fabrics of cotton, containing 85% or more by weight of cotton, unbleached")
        ]
        for code, desc in hs_data:
            if not db.query(HSCode).filter(HSCode.code == code).first():
                db.add(HSCode(code=code, description=desc, is_active=True))

        # 2. UOMs
        uoms = [
            ("NOS", "Numbers / Units", "NOS"),
            ("KGS", "Kilograms", "KGS"),
            ("LTR", "Liters", "LTR"),
            ("MTR", "Meters", "MTR"),
            ("BOX", "Box", "BOX"),
            ("BAG", "Bags", "BAG"),
            ("PKT", "Packets", "PKT")
        ]
        for code, name, fbr_code in uoms:
            if not db.query(UOM).filter(UOM.code == code).first():
                db.add(UOM(code=code, name=name, fbr_code=fbr_code, is_active=True))

        # 3. Tax Rates
        tax_rates = [
            ("Standard Sales Tax 18%", Decimal("18.00"), "SALES_TAX", "FEDERAL"),
            ("Services Sales Tax 15%", Decimal("15.00"), "SALES_TAX", "SINDH"),
            ("Reduced Rate 1%", Decimal("1.00"), "SALES_TAX", "FEDERAL"),
            ("Zero Rated / Exempt 0%", Decimal("0.00"), "SALES_TAX", "FEDERAL"),
            ("Further Tax 4%", Decimal("4.00"), "FURTHER_TAX", "FEDERAL")
        ]
        for name, rate, t_type, prov in tax_rates:
            if not db.query(TaxRate).filter(TaxRate.name == name).first():
                db.add(TaxRate(name=name, rate_percent=rate, tax_type=t_type, province=prov, is_active=True))

        # 4. Sale Types
        sale_types = [
            ("STANDARD", "Standard Rated Goods", "Standard goods subject to sales tax"),
            ("EXEMPT", "Exempt Supplies", "Goods exempt under 6th Schedule of Sales Tax Act"),
            ("ZERO_RATED", "Zero-rated Supplies", "Goods zero-rated under 5th Schedule"),
            ("SERVICES", "Taxable Services", "Services governed by provincial revenue authorities")
        ]
        for code, name, desc in sale_types:
            if not db.query(SaleType).filter(SaleType.code == code).first():
                db.add(SaleType(code=code, name=name, description=desc, is_active=True))

        # 5. Tax Profiles
        profiles = [
            ("STANDARD_GOODS", "Standard Goods Profile", Decimal("18.00"), "Default profile for taxable manufactured & imported goods"),
            ("SERVICES_SRB", "Sindh Revenue Board Services", Decimal("15.00"), "Services taxable under SRB"),
            ("EXEMPT_SUPPLIES", "Exempt Supplies", Decimal("0.00"), "Goods exempt from sales tax")
        ]
        for code, name, def_rate, desc in profiles:
            if not db.query(TaxProfile).filter(TaxProfile.code == code).first():
                db.add(TaxProfile(code=code, name=name, default_rate=def_rate, description=desc, is_active=True))

        db.flush()

        print("Seeding Demo Organization & Taxpayer...")
        # 6. Organization
        org = Organization(
            name="ABC Distribution Pvt. Ltd.",
            slug="abc-distribution",
            plan="PROFESSIONAL",
            status="ACTIVE",
            is_active=True
        )
        db.add(org)
        db.flush()

        settings = OrganizationSettings(
            organization_id=org.id,
            invoice_prefix="INV",
            next_invoice_number=1004,
            credit_note_prefix="CRN",
            debit_note_prefix="DBN",
            default_terms="Payment due within 30 days of invoice date. Official FBR digital tax invoice.",
            fbr_mode="DEMO",
            enable_auto_submit=False
        )
        db.add(settings)

        # 7. Taxpayer
        taxpayer = Taxpayer(
            tenant_id=org.id,
            legal_name="ABC Distribution Private Limited",
            trade_name="ABC Distribution",
            ntn="1234567-8",
            strn="3277876123456",
            registration_type="REGISTERED",
            business_type="WHOLESALER",
            address="Plot 42-B, Sector 15, Korangi Industrial Area",
            city="Karachi",
            province="Sindh",
            postal_code="74900",
            country="Pakistan",
            phone="+92 21 35012345",
            email="finance@abcdistribution.com",
            website="https://www.abcdistribution.example.pk",
            authorized_signatory_name="Muhammad Tariq",
            authorized_signatory_designation="Chief Financial Officer"
        )
        db.add(taxpayer)

        # 8. Branches
        main_branch = Branch(
            tenant_id=org.id,
            branch_name="Karachi Central Depot",
            branch_code="KHI-01",
            fbr_pos_id="POS-KHI-01",
            address="Plot 42-B, Sector 15, Korangi Industrial Area",
            city="Karachi",
            province="Sindh",
            phone="+92 21 35012345",
            email="depot.khi@abcdistribution.com",
            is_active=True,
            is_main=True
        )
        lhr_branch = Branch(
            tenant_id=org.id,
            branch_name="Lahore Regional Center",
            branch_code="LHR-01",
            fbr_pos_id="POS-LHR-01",
            address="Gulberg III, Main Boulevard",
            city="Lahore",
            province="Punjab",
            phone="+92 42 35789123",
            email="depot.lhr@abcdistribution.com",
            is_active=True,
            is_main=False
        )
        db.add_all([main_branch, lhr_branch])
        db.flush()

        # 9. Users
        admin_user = User(
            tenant_id=org.id,
            email="admin@abcdistribution.com",
            hashed_password=get_password_hash("Admin@123"),
            full_name="Tariq Khan (Admin)",
            role=UserRole.ORG_ADMIN.value,
            phone="+92 300 1234567",
            is_active=True
        )
        operator_user = User(
            tenant_id=org.id,
            email="operator@abcdistribution.com",
            hashed_password=get_password_hash("Operator@123"),
            full_name="Bilal Ahmed (Invoice Operator)",
            role=UserRole.INVOICE_OPERATOR.value,
            phone="+92 301 7654321",
            is_active=True
        )
        db.add_all([admin_user, operator_user])
        db.flush()

        # Seed Permanent License (No subscription expiry)
        demo_license = License(
            organization_id=org.id,
            license_number="LIC-ABCD-PERM-DEMO01",
            license_type="PERMANENT",
            status=LicenseStatus.ACTIVE.value,
            max_devices=5,
            issued_at=datetime.now(timezone.utc),
            issued_by="SUPER_ADMIN",
        )
        db.add(demo_license)
        db.flush()

        # Seed Known Demo Activation Key
        demo_key_secret = "ACT-ABCD-DEMO-2026-KEY1"
        demo_act_key = ActivationKey(
            license_id=demo_license.id,
            organization_id=org.id,
            key_hash=hash_activation_secret(demo_key_secret),
            key_prefix="ACT-ABCD-DEMO",
            status=ActivationKeyStatus.PENDING.value,
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            created_by="SUPER_ADMIN",
        )
        db.add(demo_act_key)

        # Seed FBR Credential Record (Encrypted at rest)
        demo_fbr_cred = FBRCredential(
            organization_id=org.id,
            environment="DEMO",
            provider="MOCK",
            fbr_pos_id="POS-KHI-01",
            status=FBRConnectionStatus.HEALTHY.value,
            is_active=True,
        )
        demo_fbr_cred.set_credentials(
            api_key="mock_fbr_api_key_demo_2026",
            auth_token="mock_bearer_token_demo_2026",
        )
        db.add(demo_fbr_cred)
        db.flush()

        # 10. Customers
        cust_xyz = Customer(
            tenant_id=org.id,
            created_by=admin_user.id,
            name="XYZ Traders",
            ntn="9876543-2",
            strn="3277876199999",
            registration_type="REGISTERED",
            buyer_type="B2B",
            address="Commercial Market, Hall Road",
            city="Lahore",
            province="Punjab",
            postal_code="54000",
            phone="+92 42 37210000",
            email="accounts@xyztraders.example.pk"
        )
        cust_metro = Customer(
            tenant_id=org.id,
            created_by=admin_user.id,
            name="Metro Supplies",
            ntn="5432109-8",
            strn="3277876188888",
            registration_type="REGISTERED",
            buyer_type="B2B",
            address="I.I. Chundrigar Road, City Financial Tower",
            city="Karachi",
            province="Sindh",
            postal_code="74000",
            phone="+92 21 32410000",
            email="procurement@metrosupplies.example.pk"
        )
        cust_sindh = Customer(
            tenant_id=org.id,
            created_by=admin_user.id,
            name="Sindh Wholesale Mart",
            ntn="6543210-7",
            registration_type="UNREGISTERED",
            buyer_type="B2B",
            address="Auto Bhan Road",
            city="Hyderabad",
            province="Sindh",
            phone="+92 22 2100000",
            email="info@sindhmart.example.pk"
        )
        db.add_all([cust_xyz, cust_metro, cust_sindh])
        db.flush()

        # 11. Products
        prod_a = Product(
            tenant_id=org.id,
            created_by=admin_user.id,
            item_code="POS-TERM-01",
            name="Product A - Commercial POS Terminal",
            description="All-in-one touch POS terminal with integrated customer display",
            hs_code="8471.30.10",
            uom="NOS",
            sale_type="STANDARD",
            tax_rate=Decimal("18.00"),
            unit_price=Decimal("45000.00")
        )
        prod_b = Product(
            tenant_id=org.id,
            created_by=admin_user.id,
            item_code="ROLL-THM-50",
            name="Product B - Thermal Paper Rolls (Box of 50)",
            description="80mm x 70mm premium thermal receipt paper rolls",
            hs_code="4811.90.00",
            uom="BOX",
            sale_type="STANDARD",
            tax_rate=Decimal("18.00"),
            unit_price=Decimal("3500.00")
        )
        prod_c = Product(
            tenant_id=org.id,
            created_by=admin_user.id,
            item_code="SCN-2D-IND",
            name="Product C - Industrial Barcode Scanner 2D",
            description="High speed handheld 2D QR and barcode scanner USB",
            hs_code="8471.60.20",
            uom="NOS",
            sale_type="STANDARD",
            tax_rate=Decimal("18.00"),
            unit_price=Decimal("12500.00")
        )
        prod_d = Product(
            tenant_id=org.id,
            created_by=admin_user.id,
            item_code="CASH-DRW-HD",
            name="Product D - Electronic Cash Drawer Heavy Duty",
            description="Full steel construction with RJ11 printer interface",
            hs_code="8303.00.00",
            uom="NOS",
            sale_type="STANDARD",
            tax_rate=Decimal("18.00"),
            unit_price=Decimal("8500.00")
        )
        db.add_all([prod_a, prod_b, prod_c, prod_d])
        db.flush()

        print("Seeding Invoices with FBR Submissions...")
        # 12. Invoices
        # Invoice 1: VALID / SUBMITTED to FBR with QR
        inv1_items_data = [
            {"quantity": Decimal("2"), "unit_price": Decimal("45000.00"), "discount": Decimal("2000.00"), "tax_rate": Decimal("18.00")},
            {"quantity": Decimal("4"), "unit_price": Decimal("3500.00"), "discount": Decimal("0.00"), "tax_rate": Decimal("18.00")}
        ]
        inv1_totals = PakistanTaxEngine.calculate_invoice_totals(inv1_items_data)

        inv1 = Invoice(
            tenant_id=org.id,
            created_by=admin_user.id,
            branch_id=main_branch.id,
            customer_id=cust_xyz.id,
            invoice_number="INV-KHI-01-2026-001001",
            invoice_type="TAX_INVOICE",
            invoice_date=datetime.now(timezone.utc) - timedelta(days=2),
            seller_name=taxpayer.legal_name,
            seller_ntn=taxpayer.ntn,
            seller_strn=taxpayer.strn,
            seller_branch_code=main_branch.branch_code,
            seller_province=main_branch.province,
            buyer_name=cust_xyz.name,
            buyer_ntn=cust_xyz.ntn,
            buyer_strn=cust_xyz.strn,
            buyer_registration_type=cust_xyz.registration_type,
            buyer_address=cust_xyz.address,
            buyer_province=cust_xyz.province,
            subtotal=inv1_totals["subtotal"],
            total_discount=inv1_totals["total_discount"],
            taxable_amount=inv1_totals["taxable_amount"],
            total_tax=inv1_totals["total_tax"],
            other_charges=inv1_totals["other_charges"],
            grand_total=inv1_totals["grand_total"],
            status=InvoiceStatus.VALID.value,
            fbr_status=FBRSubmissionStatus.VALID.value,
            fbr_invoice_number="FBR-20261002-841920",
            fbr_qr_data=f"FBR-DI|INV:FBR-20261002-841920|S-NTN:{taxpayer.ntn}|B-NTN:{cust_xyz.ntn}|TOT:{inv1_totals['grand_total']}|TAX:{inv1_totals['total_tax']}|DT:2026-10-02|SIG:7A8F91B2C3D4",
            fbr_submission_date=datetime.now(timezone.utc) - timedelta(days=2),
            reference_number="PO-XYZ-9041"
        )
        db.add(inv1)
        db.flush()

        it1_calc = PakistanTaxEngine.calculate_line_item(Decimal("2"), Decimal("45000.00"), Decimal("2000.00"), Decimal("18.00"))
        it1 = InvoiceItem(
            invoice_id=inv1.id,
            product_id=prod_a.id,
            item_seq=1,
            item_code=prod_a.item_code,
            description=prod_a.name,
            hs_code=prod_a.hs_code,
            quantity=Decimal("2"),
            uom=prod_a.uom,
            unit_price=Decimal("45000.00"),
            gross_amount=it1_calc["gross_amount"],
            discount=it1_calc["discount"],
            taxable_amount=it1_calc["taxable_amount"],
            tax_rate=Decimal("18.00"),
            tax_amount=it1_calc["tax_amount"],
            line_total=it1_calc["line_total"]
        )
        it2_calc = PakistanTaxEngine.calculate_line_item(Decimal("4"), Decimal("3500.00"), Decimal("0.00"), Decimal("18.00"))
        it2 = InvoiceItem(
            invoice_id=inv1.id,
            product_id=prod_b.id,
            item_seq=2,
            item_code=prod_b.item_code,
            description=prod_b.name,
            hs_code=prod_b.hs_code,
            quantity=Decimal("4"),
            uom=prod_b.uom,
            unit_price=Decimal("3500.00"),
            gross_amount=it2_calc["gross_amount"],
            discount=it2_calc["discount"],
            taxable_amount=it2_calc["taxable_amount"],
            tax_rate=Decimal("18.00"),
            tax_amount=it2_calc["tax_amount"],
            line_total=it2_calc["line_total"]
        )
        db.add_all([it1, it2])

        # FBR Submission record for inv1
        sub1 = FBRSubmission(
            tenant_id=org.id,
            created_by=admin_user.id,
            invoice_id=inv1.id,
            environment="DEMO",
            adapter_name="MockFBRAdapter",
            status="VALID",
            fbr_invoice_number="FBR-20261002-841920",
            fbr_reference="PRAL-DI-89210491",
            qr_code_data=inv1.fbr_qr_data,
            submitted_at=datetime.now(timezone.utc) - timedelta(days=2),
            responded_at=datetime.now(timezone.utc) - timedelta(days=2)
        )
        db.add(sub1)
        db.flush()

        att1 = FBRSubmissionAttempt(
            submission_id=sub1.id,
            attempt_number=1,
            http_status_code=200,
            status="VALID",
            latency_ms=142
        )
        db.add(att1)

        # Invoice 2: FAILED submission (Simulated Timeout / Retryable)
        inv2_items_data = [
            {"quantity": Decimal("1"), "unit_price": Decimal("12500.00"), "discount": Decimal("500.00"), "tax_rate": Decimal("18.00")}
        ]
        inv2_totals = PakistanTaxEngine.calculate_invoice_totals(inv2_items_data)

        inv2 = Invoice(
            tenant_id=org.id,
            created_by=operator_user.id,
            branch_id=main_branch.id,
            customer_id=cust_metro.id,
            invoice_number="INV-KHI-01-2026-001002",
            invoice_type="TAX_INVOICE",
            invoice_date=datetime.now(timezone.utc) - timedelta(hours=3),
            seller_name=taxpayer.legal_name,
            seller_ntn=taxpayer.ntn,
            seller_strn=taxpayer.strn,
            seller_branch_code=main_branch.branch_code,
            seller_province=main_branch.province,
            buyer_name=cust_metro.name,
            buyer_ntn=cust_metro.ntn,
            buyer_strn=cust_metro.strn,
            buyer_registration_type=cust_metro.registration_type,
            buyer_address=cust_metro.address,
            buyer_province=cust_metro.province,
            subtotal=inv2_totals["subtotal"],
            total_discount=inv2_totals["total_discount"],
            taxable_amount=inv2_totals["taxable_amount"],
            total_tax=inv2_totals["total_tax"],
            other_charges=inv2_totals["other_charges"],
            grand_total=inv2_totals["grand_total"],
            status=InvoiceStatus.FAILED.value,
            fbr_status=FBRSubmissionStatus.FAILED.value,
            fbr_error_code="NET-504",
            fbr_error_message="Connection to FBR Digital Invoicing Gateway timed out after 10000ms. Service temporarily unavailable.",
            reference_number="ERR-TIMEOUT-991"
        )
        db.add(inv2)
        db.flush()

        it2_1_calc = PakistanTaxEngine.calculate_line_item(Decimal("1"), Decimal("12500.00"), Decimal("500.00"), Decimal("18.00"))
        it2_1 = InvoiceItem(
            invoice_id=inv2.id,
            product_id=prod_c.id,
            item_seq=1,
            item_code=prod_c.item_code,
            description=prod_c.name,
            hs_code=prod_c.hs_code,
            quantity=Decimal("1"),
            uom=prod_c.uom,
            unit_price=Decimal("12500.00"),
            gross_amount=it2_1_calc["gross_amount"],
            discount=it2_1_calc["discount"],
            taxable_amount=it2_1_calc["taxable_amount"],
            tax_rate=Decimal("18.00"),
            tax_amount=it2_1_calc["tax_amount"],
            line_total=it2_1_calc["line_total"]
        )
        db.add(it2_1)

        sub2 = FBRSubmission(
            tenant_id=org.id,
            created_by=operator_user.id,
            invoice_id=inv2.id,
            environment="DEMO",
            adapter_name="MockFBRAdapter",
            status="FAILED",
            error_code="NET-504",
            error_message="Connection to FBR Digital Invoicing Gateway timed out after 10000ms. Service temporarily unavailable.",
            is_retryable=True,
            retry_count=0,
            submitted_at=datetime.now(timezone.utc) - timedelta(hours=3),
            responded_at=datetime.now(timezone.utc) - timedelta(hours=3)
        )
        db.add(sub2)
        db.flush()

        att2 = FBRSubmissionAttempt(
            submission_id=sub2.id,
            attempt_number=1,
            http_status_code=504,
            status="FAILED",
            error_message="Connection to FBR Gateway timed out",
            latency_ms=10012
        )
        db.add(att2)

        # Invoice 3: DRAFT invoice ready for testing
        inv3_items_data = [
            {"quantity": Decimal("1"), "unit_price": Decimal("8500.00"), "discount": Decimal("0.00"), "tax_rate": Decimal("18.00")}
        ]
        inv3_totals = PakistanTaxEngine.calculate_invoice_totals(inv3_items_data)

        inv3 = Invoice(
            tenant_id=org.id,
            created_by=admin_user.id,
            branch_id=main_branch.id,
            customer_id=cust_sindh.id,
            invoice_number="INV-KHI-01-2026-001003",
            invoice_type="TAX_INVOICE",
            invoice_date=datetime.now(timezone.utc),
            seller_name=taxpayer.legal_name,
            seller_ntn=taxpayer.ntn,
            seller_strn=taxpayer.strn,
            seller_branch_code=main_branch.branch_code,
            seller_province=main_branch.province,
            buyer_name=cust_sindh.name,
            buyer_ntn=cust_sindh.ntn,
            buyer_registration_type=cust_sindh.registration_type,
            buyer_address=cust_sindh.address,
            buyer_province=cust_sindh.province,
            subtotal=inv3_totals["subtotal"],
            total_discount=inv3_totals["total_discount"],
            taxable_amount=inv3_totals["taxable_amount"],
            total_tax=inv3_totals["total_tax"],
            other_charges=inv3_totals["other_charges"],
            grand_total=inv3_totals["grand_total"],
            status=InvoiceStatus.DRAFT.value,
            fbr_status=FBRSubmissionStatus.NOT_SUBMITTED.value,
            reference_number="PO-SM-001"
        )
        db.add(inv3)
        db.flush()

        it3_1_calc = PakistanTaxEngine.calculate_line_item(Decimal("1"), Decimal("8500.00"), Decimal("0.00"), Decimal("18.00"))
        it3_1 = InvoiceItem(
            invoice_id=inv3.id,
            product_id=prod_d.id,
            item_seq=1,
            item_code=prod_d.item_code,
            description=prod_d.name,
            hs_code=prod_d.hs_code,
            quantity=Decimal("1"),
            uom=prod_d.uom,
            unit_price=Decimal("8500.00"),
            gross_amount=it3_1_calc["gross_amount"],
            discount=it3_1_calc["discount"],
            taxable_amount=it3_1_calc["taxable_amount"],
            tax_rate=Decimal("18.00"),
            tax_amount=it3_1_calc["tax_amount"],
            line_total=it3_1_calc["line_total"]
        )
        db.add(it3_1)

        db.commit()
        print("Database successfully seeded with demo tenant, users, customers, products, and invoices!")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        if close_after:
            db.close()


if __name__ == "__main__":
    seed_database()
