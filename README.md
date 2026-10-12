# FBR Invoice Cloud --- Production SaaS Platform

**FBR Invoice Cloud** is a multi-tenant Web SaaS platform architected for Pakistani businesses to create, validate, manage, audit, and transmit digital tax invoices in compliance with the **Federal Board of Revenue (FBR)** Digital Invoicing regulations (Sales Tax Act 1990).

> **Regulatory Notice:** This application strictly separates tax invoice operations from CRM workflows. External transmission to the FBR Digital Invoicing central ledger is handled via modular adapters (Mock / Sandbox / Licensed Integrator / PRAL).

---

## Architecture Overview

```text
                      [ React 18 + TypeScript + Tailwind CSS ]
                                         │
                                   HTTP / REST
                                         ▼
                     [ FastAPI Backend Gateway (/api/v1) ]
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
 [ Auth & Tenants ]             [ Tax Invoice Engine ]             [ FBR Service ]
 - Multi-tenant context         - Line item gross/discount         - Idempotent submit
 - RBAC (Admin/Operator/Tax)    - Taxable amount calculation       - Attempt logs
 - Row-level tenant_id          - 18% GST / Provincial rates       - Exponential retry
        │                                │                                │
        └────────────────────────────────┼────────────────────────────────┘
                                         ▼
                       [ FBR Digital Invoicing Adapter ]
                                         │
                        ┌────────────────┴────────────────┐
                        ▼                                 ▼
             [ Mock / Demo Adapter ]             [ PRAL / Integrator ]
             - FBR-2026-XXXXX numbering          - Live HTTPS API
             - Digital signature QR              - Authorized tokens
             - 6 Blueprint test scenarios
```

---

## Core Capabilities Implemented

1. **Multi-Tenant SaaS Foundation**:
   - Strict organization isolation across all database queries (`tenant_id`).
   - Immutable Taxpayer profile (Legal Name, NTN, STRN, Province, Address).
   - Multi-branch support (e.g., Karachi Head Office `KHI-01`, Lahore Center `LHR-01`).
   - Server-side atomic invoice numbering (`INV-{BRANCH}-{YEAR}-{SEQ}`).

2. **Pakistan Tax Engine**:
   - Deterministic rounding (`ROUND_HALF_UP`) to 2 decimal places.
   - Formula:
     $$\text{Gross Amount} = \text{Quantity} \times \text{Unit Price}$$
     $$\text{Taxable Amount} = \text{Gross Amount} - \text{Discount}$$
     $$\text{Tax Amount} = \text{Taxable Amount} \times \frac{\text{Tax Rate \%}}{100}$$
     $$\text{Grand Total} = \sum \text{Taxable Amount} + \sum \text{Tax Amount} + \text{Other Charges}$$
   - FBR statutory reference data pre-seeded:
     - Standard 18% Federal Sales Tax, 15% SRB Provincial Services, 1% Reduced, 0% Exempt.
     - Pakistan 8-digit HS Codes (e.g. `8471.30.10`, `8517.13.00`, `4811.90.00`).
     - Standard Units of Measurement (NOS, KGS, LTR, MTR, BOX, BAG).

3. **Demo / Mock FBR Adapter**:
   - Decoupled `FBRAdapter` interface (`validate_invoice`, `submit_invoice`, `parse_response`, `get_status`).
   - `MockFBRAdapter` supporting all 6 Blueprint demo scenarios:
     1. **Valid Submission**: Generates official FBR invoice number (e.g. `FBR-20261004-981240`) and signed verification QR code.
     2. **Validation Error**: Highlights invalid NTN/STRN or missing HS codes.
     3. **FBR Rejection**: Simulates duplicate invoice reference or inactive registration.
     4. **Network Timeout**: Simulates 504 gateway timeout with `is_retryable=True`.
     5. **Pending Queue**: Simulates asynchronous fiscal batch processing.
     6. **Retry Recovery**: Successfully recovers failed or timed-out transmissions.

4. **Modern Web Frontend**:
   - Clean, high-density SaaS dashboard with KPI summary cards.
   - Dynamic Invoice creation with live tax calculations.
   - Interactive FBR Submission Center with attempt timeline and retry triggers.
   - Modal QR Code renderer for digital invoice verification.
   - Customer and Product master data management.

---

## Project Structure

```text
d:\WORKING\FB DI\main\
├── backend/
│   ├── app/
│   │   ├── core/              # Config, database, security, and auth dependencies
│   │   ├── models/            # SQLAlchemy multi-tenant models (tenant, invoice, fbr, audit)
│   │   ├── schemas/           # Pydantic v2 schemas for request validation & response
│   │   ├── adapters/          # FBRAdapter interface, MockFBRAdapter, and AdapterFactory
│   │   ├── services/          # PakistanTaxEngine, InvoiceService, FBRService, AuditService
│   │   ├── api/               # FastAPI route controllers under /api/v1
│   │   │   └── routes/        # auth, organization, branches, customers, products, invoices, fbr...
│   │   ├── seed/              # Seed script with Pakistan demo company & reference data
│   │   └── main.py            # FastAPI application entrypoint with lifespan DB initialization
│   ├── tests/                 # Pytest test suite (tax engine, tenant isolation, mock adapter)
│   ├── requirements.txt       # Python dependencies
│   ├── run.py                 # Backend runner script (Uvicorn)
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── api/               # API clients for auth, invoices, fbr, and master data
│   │   ├── context/           # AuthContext for JWT token session management
│   │   ├── components/        # Shell, Sidebar, Header, StatusBadge, QRViewerModal, SubmissionModal
│   │   ├── pages/             # Login, Dashboard, Invoices, CreateInvoice, FBR, Customers, Settings
│   │   ├── types/             # TypeScript interfaces
│   │   ├── App.tsx            # Main app router
│   │   └── main.tsx           # React DOM root
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── Dockerfile
│
├── docker-compose.yml         # Containerized Postgres, Redis, Backend, and Frontend
└── README.md
```

---

## Quickstart Guide

### 1. Backend Setup

The backend uses Python 3.11+ and FastAPI.

```bash
# Navigate to main directory
cd "d:\WORKING\FB DI\main"

# Activate the virtual environment
backend\venv\Scripts\activate

# Run test suite to verify tax engine and tenant isolation
powershell -Command "$env:PYTHONPATH='.'; backend\venv\Scripts\pytest.exe backend/tests"

# Run FastAPI backend server (listens on http://127.0.0.1:8000)
backend\venv\Scripts\python.exe backend/run.py
```

*Interactive Swagger API Documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).*

### 2. Frontend Setup

The frontend uses Vite + React 18 + Tailwind CSS.

```bash
cd "d:\WORKING\FB DI\main\frontend"

# Start the Vite development server (proxies /api to 127.0.0.1:8000)
npm.cmd run dev
```

*Frontend is accessible at [http://localhost:5173](http://localhost:5173).*

---

## Demo Credentials & Seed Data

The database is pre-seeded with Pakistani distribution company master data:

| Role | Email | Password | Organization |
| :--- | :--- | :--- | :--- |
| **Organization Admin** | `admin@abcdistribution.com` | `Admin@123` | ABC Distribution Pvt. Ltd. (NTN: 1234567-8) |
| **Invoice Operator** | `operator@abcdistribution.com` | `Operator@123` | ABC Distribution Pvt. Ltd. |

*(The Sign In screen includes one-click autofill buttons for these credentials).*

### Pre-loaded Master Data:
- **Customers**:
  - `XYZ Traders` (Lahore, Punjab - NTN: `9876543-2`, STRN: `3277876199999`)
  - `Metro Supplies` (Karachi, Sindh - NTN: `5432109-8`, STRN: `3277876188888`)
  - `Sindh Wholesale Mart` (Hyderabad, Sindh - NTN: `6543210-7`)
- **Products**:
  - `POS-TERM-01` - Commercial POS Terminal (HS: `8471.30.10`, PKR 45,000, 18% GST)
  - `ROLL-THM-50` - Thermal Receipt Paper Rolls Box of 50 (HS: `4811.90.00`, PKR 3,500, 18% GST)
  - `SCN-2D-IND` - Industrial Barcode Scanner 2D (HS: `8471.60.20`, PKR 12,500, 18% GST)
  - `CASH-DRW-HD` - Electronic Cash Drawer Heavy Duty (HS: `8303.00.00`, PKR 8,500, 18% GST)

---

## Testing Mock FBR Scenarios

When creating or submitting an invoice:
1. **Valid Submission**: Normal transmission creates a valid FBR invoice number and digitally signed verification QR code.
2. **Simulate Timeout**: Enter reference number `ERR-TIMEOUT` on the invoice. Submission returns a retryable 504 status and queues for retry. Click **Retry** in the Submission Center to test exponential recovery.
3. **Simulate Rejection**: Enter reference number `ERR-REJ`. Simulates duplicate reference rejection by FBR ledger.
4. **QR Verification**: Click the **QR Code** button on any valid invoice to view the fiscal barcode representation generated in real time.
