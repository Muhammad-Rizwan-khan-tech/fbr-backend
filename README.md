# FBR Invoice Cloud — Windows Desktop SaaS Platform & Super Admin Panel

**FBR Invoice Cloud** is an enterprise-grade multi-tenant fiscal invoicing platform for Pakistani businesses, compliant with the **Federal Board of Revenue (FBR)** Digital Invoicing regulations (Sales Tax Act 1990).

The platform consists of three core components:
1. **Windows Desktop Application**: Built with React 18, TypeScript, Tailwind CSS, and a Tauri v2 wrapper. Features first-launch hardware-bound activation, permanent license verification, dynamic backend endpoint configuration, and full offline-safe invoicing capabilities.
2. **Central Hosted Backend**: High-performance Python FastAPI service managing permanent licenses, one-time secret redemption, token rotation, AES-256-GCM encrypted FBR credentials, deterministic Pakistan tax calculation engine, and asynchronous FBR submission adapters.
3. **Laravel Super Admin Panel (`admin-panel/`)**: Standalone PHP Laravel 11 dashboard for platform owners to register customer organizations, configure authorized FBR credentials, issue permanent licenses with one-time activation secret reveals, monitor active devices, and track audit trails.

---

## Architecture Overview

```text
 ┌────────────────────────────────────────────────────────┐
 │            Windows Desktop Workstation                 │
 │   [ React 18 + TypeScript + Tailwind CSS (Tauri v2) ]  │
 │   - First-Launch Activation Screen (ACT-XXXX-...)      │
 │   - Hardware Fingerprint Binding (SHA-256)             │
 │   - Customer Dashboard, Invoices & FBR Submission      │
 └───────────────────────────┬────────────────────────────┘
                             │ HTTPS / TLS (JWT Bearer)
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │           Centrally Hosted FastAPI Backend             │
 │   - Permanent Licensing & Device Session Management    │
 │   - AES-256-GCM Encrypted FBR Integration Credentials  │
 │   - Pakistan Fiscal Engine (18% GST, ROUND_HALF_UP)    │
 │   - Multi-tenant PostgreSQL + Redis/Celery Queue       │
 └───────────────────────────▲────────────────────────────┘
                             │ Server-to-Server (X-Admin-Key)
                             │
 ┌───────────────────────────┴────────────────────────────┐
 │         PHP Laravel 11 Super Admin Panel               │
 │   - Customer Organization Management & Branches        │
 │   - Controlled One-Time Activation Key Reveal          │
 │   - FBR Credential Encryption & Live Handshake Test    │
 │   - Device Registry & Revocation Management            │
 │   - Security Audit Logs & Real-Time KPI Dashboards     │
 └────────────────────────────────────────────────────────┘
```

---

## Key Business & Security Policies

1. **Permanent License Guarantee**:
   - Customers receive lifetime permanent licenses.
   - Strictly **no recurring subscription expiry** or artificial lockouts.
   - Access continues indefinitely until explicitly revoked by an authorized platform administrator.

2. **Controlled One-Time Activation Secrets**:
   - Admins generate unique cryptographically secure keys (`ACT-XXXX-XXXX-XXXX-XXXX`).
   - The plaintext key is revealed **strictly once** in an administrative confirmation modal.
   - Stored in the backend exclusively as an irreversible `SHA-256` hash.
   - Replay prevention: Keys cannot be reused once redeemed.

3. **Client-Side Hardware Binding**:
   - On first launch, the desktop application hashes system entropy (UUID, platform, hardware specs) into a unique device fingerprint.
   - The backend atomically binds the terminal to the organization up to authorized device capacity.
   - Refresh tokens rotate atomically and enforce fingerprint consistency.

4. **Zero Client FBR Credential Exposure**:
   - Platform administrators manage FBR integration credentials centrally.
   - Credentials are encrypted at rest with `AES-256-GCM` using a 256-bit server master key.
   - Sensitive credentials are masked in all API responses (`fbr_****_9988`) and never transmitted to client desktop workstations.

5. **100% Fiscal Business Logic Preservation**:
   - Full compliance with Pakistan Sales Tax Act 1990.
   - Deterministic 2-decimal rounding with `ROUND_HALF_UP`.
   - Complete support for 8-digit HS codes, Units of Measurement, provincial tax rates (SRB, PRA, BRA, KPRA), QR code verification, and PDF invoice generation.

---

## Directory Structure

```text
├── admin-panel/             # PHP Laravel 11 Super Admin Dashboard
│   ├── app/Controllers/     # Auth, Dashboard, Organizations, Licenses, Devices, FBR, Audit
│   ├── app/Services/        # FastApiClient (Server-to-server authenticated bridge)
│   ├── resources/views/     # Tailwind CSS Blade views & Activation Key Reveal Modal
│   ├── tests/Feature/       # 100% Passing PHPUnit Feature Tests
│   ├── Dockerfile           # Alpine Nginx + PHP-FPM + Supervisor production image
│   └── composer.json
│
├── backend/                 # Python FastAPI Central Cloud Backend
│   ├── app/core/crypto.py   # AES-256-GCM encryption, secret masking, key generator
│   ├── app/models/          # License, ActivationKey, DeviceInstallation, FBRCredential, Audit
│   ├── app/services/        # LicenseService, PakistanTaxEngine, InvoiceService, FBRService
│   ├── app/api/routes/      # activation.py (desktop client), admin.py (super admin panel)
│   ├── tests/               # 55 Passing Pytest Unit & End-to-End Tests
│   └── requirements.txt
│
├── frontend/                # React 18 + TypeScript Desktop Frontend
│   ├── src/pages/           # ActivationPage, LoginPage, DashboardPage, InvoicesPage, FBR...
│   ├── src/context/         # AuthContext (Activation, tokens, session restoration)
│   ├── src/api/client.ts    # Configurable HTTPS base URL, token rotation interceptor
│   ├── src/utils/           # fingerprint.ts (Hardware UUID & Windows OS entropy)
│   └── src-tauri/           # Tauri v2 Windows Desktop Wrapper configuration & Rust lib
│
├── scripts/
│   └── build_desktop.bat    # Windows desktop binary & installer builder
│
├── docker-compose.yml       # Production container orchestration
└── README.md
```

---

## Getting Started & Local Development

### 1. Central Backend (FastAPI)

```bash
# Activate virtual environment
backend\venv\Scripts\activate

# Run database migrations / seed
python -m backend.app.seed.seed_data

# Start FastAPI server
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be available at `http://127.0.0.1:8000/docs`.

### 2. Super Admin Panel (Laravel)

```bash
cd admin-panel

# Install dependencies (if not cached)
composer install

# Migrate database
php artisan migrate

# Seed Super Admin credentials
php artisan db:seed

# Start Laravel development server
php artisan serve --port 8080
```
- Admin Panel URL: `http://127.0.0.1:8080`
- Default Super Admin: `superadmin@fbrinvoicecloud.com`
- Default Password: `SuperAdmin@Secure2026!`

### 3. Desktop Application (React / Tauri)

```bash
cd frontend

# Install npm dependencies
npm install

# Start development server
npm run dev

# Or build production desktop package
npm run build
```

---

## Verifying the Test Suites

Both the backend and administrative frontend include complete automated test suites:

### FastAPI Backend Tests (55 Tests — 100% Pass)
```powershell
backend\venv\Scripts\python.exe -m pytest
```
Covers:
- `test_licensing_and_activation.py`: AES-256-GCM encryption, one-time secret generation, replay prevention, device limits, token rotation, license revocation, and full E2E desktop activation to invoice generation.
- `test_e2e_full_system.py`: Multi-tenant fiscal engine, 18% GST calculations, PDF invoices, signed downloads, QR codes.
- `test_fbr_adapters.py`: All 6 FBR submission scenarios (Valid, Error, Rejection, Timeout, Pending, Recovery).
- `test_tenant_isolation.py`: Cross-tenant database partition security.

### Laravel Super Admin Tests (7 Tests — 100% Pass)
```powershell
$env:PATH = "e:\tools\php;$env:PATH"
e:\tools\php\php.exe artisan test
```
Covers:
- Guest redirection & route protection
- Super Admin authentication & credential validation
- FastApiClient mocked KPI rendering & service integration
- Organizations registry data display

---

## Production Deployment with Docker Compose

To deploy all central services using Docker:

```bash
docker-compose up -d --build
```

Services started:
- `fbr_backend`: FastAPI running on port 8000
- `fbr_admin_panel`: Nginx + PHP-FPM running on port 8080
- `fbr_postgres`: PostgreSQL 16 database running on port 5432
- `fbr_redis`: Redis 7 cache and job broker running on port 6379

---

## Step-by-Step Operator Workflow

1. **Log in to Super Admin**: Navigate to `http://localhost:8080` and log in with your administrative credentials.
2. **Register Customer Organization**: Go to **Organizations** &rarr; **New Organization**. Fill in the company's NTN, legal name, province, and authorized terminal count.
3. **Configure FBR Credentials**: Select FBR environment (Demo, Sandbox, or Production) and configure POS ID and authentication tokens (securely encrypted with AES-256-GCM).
4. **Copy Activation Secret**: The platform generates and reveals a one-time key (e.g. `ACT-3X9K-8F2Q-11MZ-77PA`). Securely copy and deliver this key to the customer.
5. **Customer Desktop Launch**: The customer opens the Windows desktop app, enters the activation key and workstation terminal name, and clicks **Activate**.
6. **Automatic Verification**: The backend validates the secret, locks the hardware fingerprint, issues a permanent license token, and immediately displays the customer's live invoicing dashboard.
