import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_full_api_workflow():
    # 1. Health Check
    health_res = client.get("/health")
    assert health_res.status_code == 200
    print("[PASS] /health endpoint")

    # 2. Login as Demo Admin
    login_res = client.post("/api/v1/auth/login", json={
        "email": "admin@abcdistribution.com",
        "password": "Admin@123"
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token_data = login_res.json()
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[PASS] Authentication successful for tenant: {token_data['org_name']}")

    # 3. Check Dashboard KPIs
    kpis_res = client.get("/api/v1/reports/dashboard-kpis", headers=headers)
    assert kpis_res.status_code == 200
    kpis = kpis_res.json()
    print(f"[PASS] Dashboard KPIs: {kpis['monthly_invoices_count']} invoices, Total Tax: PKR {kpis['total_tax']:,.2f}")

    # 4. List Invoices
    inv_list_res = client.get("/api/v1/invoices", headers=headers)
    assert inv_list_res.status_code == 200
    invoices = inv_list_res.json()
    assert len(invoices) >= 3
    print(f"[PASS] Invoices listing returned {len(invoices)} invoices")

    # 5. Get Branches, Customers, Products
    branches = client.get("/api/v1/branches", headers=headers).json()
    customers = client.get("/api/v1/customers", headers=headers).json()
    products = client.get("/api/v1/products", headers=headers).json()
    assert len(branches) > 0 and len(customers) > 0 and len(products) > 0
    print(f"[PASS] Master data loaded: {len(branches)} branches, {len(customers)} customers, {len(products)} products")

    # 6. Create a New Invoice
    new_inv_payload = {
        "branch_id": branches[0]["id"],
        "customer_id": customers[0]["id"],
        "invoice_type": "TAX_INVOICE",
        "reference_number": "PO-TEST-2026",
        "items": [
            {
                "product_id": products[0]["id"],
                "item_code": products[0]["item_code"],
                "description": products[0]["name"],
                "hs_code": products[0]["hs_code"],
                "quantity": 3,
                "uom": products[0]["uom"],
                "unit_price": 45000.00,
                "discount": 1000.00,
                "tax_rate": 18.00,
                "sale_type": "STANDARD"
            }
        ]
    }
    create_res = client.post("/api/v1/invoices", json=new_inv_payload, headers=headers)
    assert create_res.status_code == 201, f"Create invoice failed: {create_res.text}"
    created_inv = create_res.json()
    print(f"[PASS] Invoice created: {created_inv['invoice_number']} (Grand Total: PKR {float(created_inv['grand_total']):,.2f})")

    # 7. Submit Invoice to Mock FBR Adapter
    submit_res = client.post(f"/api/v1/invoices/{created_inv['id']}/submit", headers=headers)
    assert submit_res.status_code == 200, f"FBR submission failed: {submit_res.text}"
    sub_data = submit_res.json()
    assert sub_data["status"] == "VALID"
    assert sub_data["fbr_invoice_number"] is not None
    print(f"[PASS] FBR Transmission Succeeded! Assigned FBR No: {sub_data['fbr_invoice_number']}")

    # 8. Check QR Code endpoint
    qr_res = client.get(f"/api/v1/invoices/{created_inv['id']}/qr", headers=headers)
    assert qr_res.status_code == 200
    assert qr_res.headers["content-type"] == "image/png"
    print(f"[PASS] FBR QR Code image successfully generated ({len(qr_res.content)} bytes)")

    print("\n[SUCCESS] ALL END-TO-END WORKFLOW TESTS PASSED!")

if __name__ == "__main__":
    test_full_api_workflow()
