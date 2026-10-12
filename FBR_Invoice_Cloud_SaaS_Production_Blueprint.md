# FBR Invoice Cloud --- Production SaaS Blueprint

**Product:** FBR Invoice Cloud\
**Type:** Multi-tenant Web SaaS\
**Market:** Pakistan\
**Purpose:** Digital tax invoicing and FBR integration\
**Scope:** Standalone invoicing platform --- **not a CRM**

## 1. Product Definition

FBR Invoice Cloud is a browser-based SaaS platform for businesses to
create, validate, manage, render, audit, and transmit tax invoices and
related documents through the legally appropriate FBR digital-invoicing
integration route.

Core capabilities:

-   Multi-tenant SaaS accounts
-   Company/taxpayer and branch setup
-   Users, roles and permissions
-   Customer/buyer master data
-   Product/item master data
-   HS codes, UOM, sale types and tax profiles
-   Tax invoice creation and validation
-   FBR submission workflow
-   Submission status, errors and retries
-   Credit and debit notes
-   PDF invoices and QR representation
-   Tax and submission reports
-   Audit trail
-   API/webhooks for higher plans
-   SaaS billing and usage controls

**Explicitly excluded:** leads, CRM pipelines, opportunities, marketing
automation, CRM sales orders and other CRM features.

> **Regulatory boundary:** The application must not claim to be FBR or
> an FBR licensed integrator unless the operating entity actually holds
> the required authorization. FBR's current FAQ states that notified
> registered persons' POS/ERP/invoicing systems are integrated through a
> licensed integrator, while PRAL is also designated as a licensed
> integrator under applicable rules.

------------------------------------------------------------------------

# 2. Regulatory Integration Strategy

FBR publishes digital-invoicing technical/API documentation, a user
manual, FAQs and a current licensed-integrator list. Production
integration must use the applicable authorized route.

Official sources:

-   FBR Technical Assistance:
    https://www.fbr.gov.pk/di-technical-assistance/173967/173970
-   FBR User Manual:
    https://www.fbr.gov.pk/di-technical-assistance/173967/174202
-   FBR Licensed Integrators:
    https://www.fbr.gov.pk/list-of-license-interprator/173967/173971
-   FBR FAQs: https://www.fbr.gov.pk/faqs/173967/173969

### FBR Adapter Architecture

``` text
Invoice Engine
      |
      v
FBR Adapter Interface
      |
      +-- Mock/Sandbox Adapter
      +-- Licensed Integrator Adapter
      +-- PRAL/approved integration adapter
```

Do not scatter FBR API calls through invoice screens. FBR-specific logic
belongs behind an adapter so the SaaS core remains stable if integration
arrangements change.

------------------------------------------------------------------------

# 3. SaaS Architecture

``` text
Internet
   |
CDN / WAF
   |
Load Balancer
   |
Web Frontend
   |
FastAPI Application
   |
+-------------------------------+
| Auth | Tenant | Invoice | Tax |
| FBR  | Reports | Billing      |
+-------------------------------+
   |
PostgreSQL
   |
Redis / Queue
   |
Background Workers
   |
Object Storage

FBR Worker
   |
FBR Adapter
   |
Authorized Integration Route
   |
FBR / PRAL
```

### Recommended stack

**Frontend**

-   React
-   TypeScript
-   Next.js or Vite
-   Tailwind CSS
-   TanStack Query
-   React Hook Form
-   Zod

**Backend**

-   Python
-   FastAPI
-   Pydantic
-   SQLAlchemy
-   Alembic

**Infrastructure**

-   PostgreSQL
-   Redis
-   Celery or equivalent worker system
-   Object storage
-   CDN/WAF
-   Containerized deployment
-   Secrets manager
-   Monitoring and centralized logs
-   Automated backups

Recommended combination:

**React/Next.js + FastAPI + PostgreSQL + Redis**

------------------------------------------------------------------------

# 4. Multi-Tenant SaaS Model

Each customer is an isolated organization/tenant.

``` text
Platform
|
+-- Tenant A
|   +-- Company
|   +-- Branches
|   +-- Users
|   +-- Customers
|   +-- Products
|   +-- Invoices
|
+-- Tenant B
|   +-- Company
|   +-- Branches
|   +-- Users
|   +-- Customers
|   +-- Products
|   +-- Invoices
```

Every tenant-owned record must include `tenant_id`.

Tenant isolation must be enforced at:

1.  Authentication
2.  API authorization
3.  Service layer
4.  Repository/query layer
5.  Database policy where practical

No tenant may access another tenant's:

-   invoices
-   buyers
-   products
-   reports
-   FBR credentials
-   audit logs
-   PDFs
-   integration configuration

------------------------------------------------------------------------

# 5. SaaS Plans

## Starter

-   1 organization
-   1 branch
-   Limited users
-   Limited monthly invoices
-   PDF invoices
-   Basic reports

## Professional

-   Multiple branches
-   More users
-   Higher invoice volume
-   FBR submission workflow
-   Credit/debit notes
-   Advanced reports
-   API access
-   Audit history

## Business

-   Higher invoice volume
-   Multiple branches
-   Bulk import
-   API and webhooks
-   Advanced reporting
-   Automated backup options

## Enterprise

-   Custom volume
-   Dedicated support
-   SSO
-   Dedicated infrastructure option
-   Custom integrations
-   Advanced API
-   Custom SLA

Plan limits must be enforced by backend entitlements, not merely hidden
UI elements.

------------------------------------------------------------------------

# 6. Application Modules

## Workspace

1.  Dashboard
2.  Invoices
3.  Credit Notes
4.  Debit Notes
5.  Customers
6.  Products
7.  Tax Configuration
8.  FBR Submission Center
9.  Reports

## Administration

10. Company Setup
11. Branches
12. Users & Roles
13. Audit Log
14. Subscription & Billing
15. Integration Settings
16. System Settings

------------------------------------------------------------------------

# 7. Authentication

Screens:

-   Registration
-   Login
-   Email verification
-   Forgot password
-   Reset password
-   Optional MFA

Security:

-   Argon2id/bcrypt password hashing
-   Secure sessions/tokens
-   Refresh-token rotation where applicable
-   Rate limiting
-   Login-attempt protection
-   MFA option

------------------------------------------------------------------------

# 8. First-Time Setup Wizard

``` text
1. Create Organization
2. Company / Taxpayer Information
3. Branch
4. FBR Integration
5. Reference Data
6. Invoice Branding
7. Invite Users
8. Finish
```

Show completion status for:

-   Company
-   Branch
-   Integration
-   Tax configuration
-   Product setup
-   First customer
-   Ready-to-invoice state

------------------------------------------------------------------------

# 9. Dashboard

KPI cards:

-   Today's invoices
-   Monthly invoices
-   Valid FBR invoices
-   Pending submissions
-   Failed submissions
-   Taxable amount
-   Total tax
-   Credit notes
-   Debit notes

Sections:

### Recent invoices

Invoice \# \| Date \| Buyer \| Amount \| Tax \| FBR Status \| Action

### FBR status

``` text
CONNECTED
Environment: Production
Last successful submission: ...
Pending queue: 0
```

### Failed submissions

Show invoice, error code, short message and retry action.

### Quick actions

-   New Invoice
-   New Credit Note
-   New Debit Note
-   Add Customer
-   Add Product
-   View Submissions

------------------------------------------------------------------------

# 10. Company and Taxpayer Setup

Fields:

-   Legal business name
-   NTN
-   STRN
-   Registration type
-   Business type
-   Address
-   City
-   Province
-   Postal code
-   Country
-   Phone
-   Email
-   Website
-   Tax registration data
-   Invoice prefix
-   Numbering policy

Branding:

-   Logo
-   Company name
-   Address
-   Footer
-   Authorized-signatory text
-   Invoice template

------------------------------------------------------------------------

# 11. Branch Management

Fields:

-   Branch name
-   Branch code
-   Address
-   Province
-   City
-   Phone
-   Email
-   Tax identifiers
-   Active/inactive
-   Invoice numbering configuration

Branch permissions and reporting must be supported.

------------------------------------------------------------------------

# 12. User Roles

### Super Admin

Everything.

### Organization Admin

Organization, settings and users.

### Invoice Operator

Create/manage invoices.

### Tax Officer

Tax configuration, validation, reports and submissions.

### Accountant

Invoices, notes and reports.

### Viewer

Read-only.

Support custom roles for Enterprise.

------------------------------------------------------------------------

# 13. Customer / Buyer Master

This is **invoice master data, not CRM**.

Fields:

-   Customer name
-   NTN
-   STRN
-   CNIC where legally applicable
-   Registration type
-   Province
-   City
-   Address
-   Phone
-   Email
-   Buyer reference
-   Active status

Actions:

-   Add
-   Edit
-   View
-   Archive
-   Search
-   Import
-   Export

------------------------------------------------------------------------

# 14. Product / Item Master

Fields:

-   Item code
-   Product name
-   Description
-   HS code
-   UOM
-   Sale type
-   Tax profile
-   Tax rate
-   SRO/reference information
-   Unit price
-   Active status

Optional:

-   SKU
-   Barcode
-   Category
-   Brand
-   Packaging
-   Minimum/maximum price

------------------------------------------------------------------------

# 15. FBR Reference Data

Dedicated tabs:

-   HS Codes
-   UOM
-   Tax Rates
-   Sale Types
-   Tax Profiles
-   SRO / Rule References
-   Provinces
-   Scenario/reference values

Each reference dataset should support:

-   Source
-   Version
-   Effective date
-   Active flag
-   Last synchronized date

Tax/reference rules must be versioned and not hard-coded into React
components.

------------------------------------------------------------------------

# 16. Tax Engine

Responsibilities:

-   Taxable amount
-   Discounts
-   Tax calculation
-   Applicable additional charges
-   Invoice totals
-   Tax profile validation
-   Scenario validation
-   FBR payload preparation

Basic calculation:

``` text
Quantity x Unit Price
        =
Gross Line Amount

Gross Amount - Discount
        =
Taxable Amount

Taxable Amount x Applicable Rate
        =
Tax Amount
```

Actual FBR-specific rules must follow the current official specification
for the taxpayer scenario.

------------------------------------------------------------------------

# 17. New Tax Invoice

### Header

-   Invoice type
-   Invoice date
-   Branch
-   Buyer
-   NTN/STRN
-   Registration status
-   Province
-   Reference number
-   Notes

### Item grid

-   Item
-   Description
-   HS Code
-   Quantity
-   UOM
-   Unit Price
-   Discount
-   Tax Rate
-   Tax Amount
-   Line Total

### Totals

-   Subtotal
-   Discount
-   Taxable amount
-   Tax
-   Other applicable charges
-   Grand total

### Actions

-   Save Draft
-   Validate
-   Submit
-   Save & New
-   Print Preview

------------------------------------------------------------------------

# 18. Invoice Lifecycle

``` text
DRAFT
  |
  v
VALIDATING
  |
  +---- INVALID ---> CORRECTION
  |
  v
READY
  |
  v
SUBMITTING
  |
  +---- FAILED ---> RETRY / CORRECT
  |
  v
SUBMITTED
  |
  v
FBR RESPONSE
  |
  +---- VALID
  +---- INVALID
  +---- REJECTED
```

Every transition must be auditable.

------------------------------------------------------------------------

# 19. Validation Layers

### Frontend

-   Required fields
-   Data types
-   Quantity
-   Price
-   Buyer/product selection

### Backend

-   Tenant ownership
-   Permissions
-   Tax configuration
-   Reference-data validity
-   Invoice numbering
-   Duplicate detection

### FBR adapter

-   Required payload fields
-   Current scenario rules
-   Provider authentication
-   Provider/FBR validation

------------------------------------------------------------------------

# 20. FBR Submission Center

Filters:

-   Date
-   Branch
-   Buyer
-   Status
-   Invoice number
-   FBR invoice number
-   Error code

Statuses:

-   Draft
-   Ready
-   Pending
-   Submitted
-   Valid
-   Invalid
-   Failed
-   Cancelled

Actions:

-   View
-   Retry
-   Correct
-   Download
-   Print
-   Technical details

------------------------------------------------------------------------

# 21. Submission Detail

Display:

### Invoice

-   Internal ID
-   Invoice number
-   Date
-   Buyer
-   Amount

### Integration

-   Adapter/provider
-   Environment
-   Request ID
-   Submission timestamp
-   Response timestamp
-   FBR reference
-   FBR invoice number
-   Status

### Timeline

``` text
Created
Validated
Submitted
Response received
Valid / Invalid / Failed
```

Store raw responses securely but display sanitized, human-readable
details.

------------------------------------------------------------------------

# 22. Error and Retry System

Each error should contain:

-   Internal error ID
-   FBR/provider error code
-   User-readable message
-   Technical message
-   Severity
-   Retryable flag
-   Timestamp
-   Invoice reference
-   Correlation ID

Automatic retry is appropriate for temporary failures such as timeout or
temporary service unavailability.

Manual correction is required for validation/business-rule failures.

Use exponential backoff.

------------------------------------------------------------------------

# 23. Offline/Connectivity Architecture

If offline invoicing is required by the applicable business and
regulatory scenario:

``` text
Internet unavailable
      |
      v
Offline-mode invoice
      |
      v
Safe local queue
      |
      v
Connection restored
      |
      v
Upload within required regulatory window
```

The exact behavior must follow the current FBR rules/specification; do
not implement offline compliance assumptions.

------------------------------------------------------------------------

# 24. Credit Notes

Fields:

-   Credit note number
-   Date
-   Original invoice
-   Reason
-   Buyer
-   Items
-   Quantity
-   Tax impact
-   Total
-   Supporting reference

Workflow:

``` text
Draft -> Validate -> Submit -> FBR Response
```

------------------------------------------------------------------------

# 25. Debit Notes

Same architecture as credit notes, with:

-   Original invoice reference
-   Reason
-   Adjustment
-   Tax adjustment
-   Submission response
-   Audit history

------------------------------------------------------------------------

# 26. Invoice PDF

A final PDF should contain, as applicable:

-   Company information
-   Taxpayer information
-   Buyer information
-   Invoice number
-   Date
-   Items
-   HS codes
-   Quantity
-   UOM
-   Price
-   Tax
-   Total
-   FBR invoice/reference information
-   QR representation
-   Verification information
-   Footer/terms

Use server-side deterministic rendering.

Store immutable copies of finalized documents where appropriate.

------------------------------------------------------------------------

# 27. QR Architecture

``` text
Invoice/FBR Response
        |
QR Payload Builder
        |
QR Renderer
        |
PDF / Invoice UI
```

The QR payload must follow the current FBR technical specification.
Never invent or assume the production payload format.

------------------------------------------------------------------------

# 28. Reports

-   Invoice Register
-   FBR Submission Report
-   Tax Summary
-   Customer Invoice Report
-   Product Tax Report
-   Credit Note Report
-   Debit Note Report
-   Failed Submission Report
-   Daily/Monthly/Quarterly/Yearly reports

Export:

-   CSV
-   Excel
-   PDF

------------------------------------------------------------------------

# 29. Audit Log

Record:

-   Login/logout
-   User changes
-   Permission changes
-   Company changes
-   Branch changes
-   Customer/product changes
-   Tax configuration changes
-   Invoice creation/edit/validation
-   FBR submission/response/retry
-   Credit/debit notes
-   PDF generation
-   API key creation
-   Integration configuration
-   Subscription changes

Audit record:

``` text
ID
Tenant
User
Action
Entity
Entity ID
Timestamp
IP
User Agent
Before
After
Correlation ID
```

Sensitive compliance history should be append-only.

------------------------------------------------------------------------

# 30. Database Architecture

Use **PostgreSQL**.

Core tables:

``` text
organizations
organization_settings
subscriptions
subscription_usage

users
roles
permissions
user_roles

branches
taxpayers

tax_profiles
tax_rates
hs_codes
uoms
sale_types
sro_references
reference_data_versions

customers
products

invoices
invoice_items
invoice_totals

credit_notes
credit_note_items

debit_notes
debit_note_items

fbr_submissions
fbr_submission_attempts
fbr_responses

invoice_documents
qr_payloads

notifications
audit_logs

api_keys
webhook_endpoints

integration_configs
integration_credentials

background_jobs
system_events
```

Tenant-owned tables should include:

``` text
tenant_id
created_at
updated_at
created_by
updated_by
```

Use UUIDs, foreign keys, indexes, unique constraints, migrations and
transaction boundaries.

------------------------------------------------------------------------

# 31. Invoice Numbering

Invoice numbering must be generated server-side.

Consider:

-   tenant
-   branch
-   invoice series
-   financial period where required

Use transaction-safe counters. Never generate official invoice numbers
only in the browser.

------------------------------------------------------------------------

# 32. API Architecture

Base:

`/api/v1`

### Auth

``` http
POST /auth/register
POST /auth/login
POST /auth/logout
POST /auth/refresh
POST /auth/forgot-password
POST /auth/reset-password
```

### Organization

``` http
GET   /organization
PATCH /organization
```

### Customers

``` http
GET   /customers
POST  /customers
GET   /customers/{id}
PATCH /customers/{id}
```

### Products

``` http
GET   /products
POST  /products
GET   /products/{id}
PATCH /products/{id}
```

### Tax

``` http
GET /tax/profiles
GET /tax/rates
GET /tax/hs-codes
GET /tax/uoms
GET /tax/sale-types
```

### Invoices

``` http
GET  /invoices
POST /invoices
GET  /invoices/{id}
PATCH /invoices/{id}
POST /invoices/{id}/validate
POST /invoices/{id}/submit
POST /invoices/{id}/retry
GET  /invoices/{id}/pdf
```

### FBR

``` http
GET  /fbr/status
GET  /fbr/submissions
GET  /fbr/submissions/{id}
POST /fbr/test-connection
```

### Notes

``` http
GET  /credit-notes
POST /credit-notes
GET  /debit-notes
POST /debit-notes
```

### Reports

``` http
GET /reports/invoices
GET /reports/tax-summary
GET /reports/fbr-submissions
GET /reports/failed-submissions
```

------------------------------------------------------------------------

# 33. FBR Adapter Interface

Conceptual backend contract:

``` python
class FBRAdapter:

    def validate_invoice(self, invoice):
        ...

    def submit_invoice(self, invoice):
        ...

    def get_reference_data(self):
        ...

    def parse_response(self, response):
        ...

    def get_status(self, submission_id):
        ...
```

Possible adapters:

``` text
MockFBRAdapter
SandboxFBRAdapter
LicensedIntegratorAdapter
PRALAdapter
```

Production adapter behavior must match the currently approved
integration protocol.

------------------------------------------------------------------------

# 34. Background Workers

Use workers for:

-   FBR submissions
-   Retries
-   PDF generation
-   Report generation
-   Reference-data synchronization
-   Notifications
-   Usage metering
-   Scheduled cleanup
-   Backup verification
-   Webhook delivery

Architecture:

``` text
API
 |
Redis Queue
 |
+-- invoice-worker
+-- pdf-worker
+-- report-worker
+-- notification-worker
+-- sync-worker
```

------------------------------------------------------------------------

# 35. Idempotency

Critical submission APIs must support idempotency.

Example:

``` http
Idempotency-Key: <unique-key>
```

Use:

-   idempotency key
-   invoice fingerprint
-   submission state
-   provider reference
-   correlation ID

This prevents duplicate submissions after network timeouts.

------------------------------------------------------------------------

# 36. Webhooks and External API

Higher plans may provide:

``` text
invoice.created
invoice.validated
invoice.submitted
invoice.valid
invoice.failed
invoice.rejected
credit_note.submitted
debit_note.submitted
integration.status_changed
```

Webhook requirements:

-   signed payloads
-   retries
-   delivery history
-   idempotency
-   timeout handling
-   disabled-endpoint handling

------------------------------------------------------------------------

# 37. Billing

Billing must remain separate from tax logic.

Architecture:

``` text
Subscription
    |
Plan
    |
Usage Meter
    |
Payment
    |
Entitlements
```

Track:

-   invoice count
-   users
-   branches
-   API calls
-   storage
-   report usage

Billing provider should be replaceable.

------------------------------------------------------------------------

# 38. Security

### Application

-   HTTPS
-   secure cookies/tokens
-   CSRF protection where applicable
-   XSS protection
-   input validation
-   output encoding
-   rate limiting
-   brute-force protection

### Database

-   encryption at rest
-   encrypted backups
-   least-privilege DB access
-   private networking

### Secrets

Never place FBR credentials in source code.

Use a secrets manager such as:

-   AWS Secrets Manager
-   Azure Key Vault
-   GCP Secret Manager
-   HashiCorp Vault

Never log:

-   passwords
-   tokens
-   API secrets
-   FBR credentials
-   private keys

------------------------------------------------------------------------

# 39. Data Protection

Protect:

-   NTN
-   STRN
-   buyer information
-   business information
-   financial information
-   integration credentials

Use:

-   encryption in transit
-   encryption at rest
-   RBAC
-   audit logs
-   retention policies
-   secure deletion

------------------------------------------------------------------------

# 40. Object Storage

Store:

-   invoice PDFs
-   reports
-   logos
-   exports
-   approved attachments

Example:

``` text
tenant/{tenant_id}/
  invoices/{year}/{month}/
  credit-notes/
  debit-notes/
  reports/
  branding/
```

Use signed URLs. Never expose raw storage paths publicly.

------------------------------------------------------------------------

# 41. Frontend Structure

``` text
src/
+-- app/
+-- components/
+-- layouts/
+-- pages/
+-- features/
|   +-- auth/
|   +-- dashboard/
|   +-- invoices/
|   +-- customers/
|   +-- products/
|   +-- taxes/
|   +-- fbr/
|   +-- reports/
|   +-- settings/
+-- api/
+-- hooks/
+-- schemas/
+-- types/
+-- utils/
+-- permissions/
+-- styles/
```

------------------------------------------------------------------------

# 42. Backend Structure

``` text
backend/
+-- app/
    +-- api/
    +-- auth/
    +-- tenants/
    +-- users/
    +-- branches/
    +-- customers/
    +-- products/
    +-- taxes/
    +-- invoices/
    +-- credit_notes/
    +-- debit_notes/
    +-- fbr/
    +-- reports/
    +-- billing/
    +-- audit/
    +-- notifications/
    +-- storage/
    +-- workers/
    +-- integrations/
    +-- common/
```

------------------------------------------------------------------------

# 43. Domain Separation

Keep:

``` text
UI
 |
API
 |
Invoice Service
 |
Tax Engine
 |
Invoice Repository
 |
FBR Payload Builder
 |
FBR Adapter
```

Never calculate tax inside React.

Never call FBR directly from an invoice form.

------------------------------------------------------------------------

# 44. UI/UX Design System

Style:

-   professional light SaaS UI
-   white cards
-   neutral background
-   readable dark text
-   single primary accent
-   subtle borders
-   medium-radius controls
-   compact forms
-   readable data tables
-   semantic status badges

Main shell:

``` text
+------------------------------------------------------+
| Logo | Search | Notifications | Help | User         |
+-----------+------------------------------------------+
|           |                                          |
| Dashboard |              Workspace                   |
| Invoices  |                                          |
| Customers |                                          |
| Products  |                                          |
| Tax       |                                          |
| FBR       |                                          |
| Reports   |                                          |
|           |                                          |
| Admin     |                                          |
| Settings  |                                          |
+-----------+------------------------------------------+
```

Desktop-first, responsive for tablet/mobile.

------------------------------------------------------------------------

# 45. Invoice Table

Columns:

``` text
Invoice #
Date
Buyer
Branch
Taxable Amount
Tax
Total
FBR Status
Actions
```

Actions:

-   View
-   Edit
-   Duplicate
-   PDF
-   Submit
-   Retry
-   Credit Note
-   Debit Note

Invoice detail tabs:

1.  Overview
2.  Items
3.  Tax
4.  FBR Submission
5.  Documents
6.  Audit

------------------------------------------------------------------------

# 46. FBR Connection Screen

``` text
Integration Status
------------------
CONNECTED

Provider
Configured licensed integration provider

Environment
Sandbox / Production

Last successful communication
...

Pending submissions
...

Test Connection
```

Never display secrets.

------------------------------------------------------------------------

# 47. Demo Mode

Implement a completely separate Demo/Mock mode.

Scenarios:

1.  Valid invoice
2.  Validation error
3.  FBR rejection
4.  Network timeout
5.  Pending response
6.  Retry success

Demo mode must never send demo records to production FBR.

Seed data can use:

-   ABC Distribution Pvt. Ltd.
-   XYZ Traders
-   Metro Supplies
-   Sindh Wholesale Mart
-   Product A-D

------------------------------------------------------------------------

# 48. Platform Admin Portal

Separate from customer UI.

Functions:

-   Organizations
-   Users
-   Plans
-   Subscriptions
-   Usage
-   System health
-   Integration health
-   Failed jobs
-   Support
-   Audit
-   Feature flags

Support access to customer data must be explicit and audited.

------------------------------------------------------------------------

# 49. Observability

Track:

-   API latency
-   queue depth
-   FBR success rate
-   FBR failure rate
-   response time
-   database health
-   worker health
-   storage health
-   login anomalies

Metrics:

``` text
Invoices/hour
Submissions/hour
Valid rate
Failure rate
Average FBR response time
Queue latency
API error rate
```

------------------------------------------------------------------------

# 50. Backups and Disaster Recovery

PostgreSQL:

-   automated backups
-   point-in-time recovery where available
-   encrypted backups
-   off-site backup
-   periodic restore tests

Define:

-   RPO
-   RTO

Example targets:

``` text
RPO: 15 minutes
RTO: 2 hours
```

Final SLA depends on infrastructure budget.

------------------------------------------------------------------------

# 51. CI/CD

``` text
Developer
  |
Git
  |
Pull Request
  |
Tests
  |
Security Scan
  |
Build
  |
Docker Image
  |
Staging
  |
Acceptance Tests
  |
Production
```

Checks:

-   unit tests
-   integration tests
-   frontend tests
-   migrations
-   linting
-   dependency scanning
-   container scanning

------------------------------------------------------------------------

# 52. Environments

Maintain:

``` text
Development
Testing
Staging
Production
```

Never connect development to production FBR credentials.

------------------------------------------------------------------------

# 53. Testing Strategy

### Unit

-   tax calculations
-   invoice totals
-   permissions
-   numbering
-   validation
-   FBR response parsing

### Integration

-   PostgreSQL
-   Redis
-   workers
-   FBR adapter
-   PDF generation

### End-to-end

``` text
Login
→ Setup
→ Customer
→ Product
→ Invoice
→ Validate
→ Submit
→ Response
→ PDF
→ Report
```

### Security

-   tenant isolation
-   IDOR
-   authentication
-   authorization
-   rate limiting
-   injection
-   XSS
-   CSRF
-   file access

------------------------------------------------------------------------

# 54. Critical Acceptance Tests

### Tenant isolation

Tenant A can never retrieve Tenant B data.

### Calculation

Known inputs always produce deterministic totals.

### Duplicate protection

Repeated submission does not create a duplicate.

### Failed submission

Invoice, request, response, error and retry history remain preserved.

### PDF

Final PDF exactly reflects stored invoice data.

### Audit

Critical changes are traceable.

------------------------------------------------------------------------

# 55. Development Roadmap

## Phase 0 --- Regulatory/Technical Discovery

-   Review current FBR legal provisions
-   Review current API documentation
-   Review user manual
-   Confirm licensed-integrator arrangement
-   Map taxpayer scenarios
-   Map required payload fields
-   Define sandbox strategy

**Deliverable:** frozen integration specification.

## Phase 1 --- SaaS Foundation

-   Authentication
-   Organizations
-   Users
-   Roles
-   Tenant isolation
-   Subscription foundation
-   Dashboard shell
-   Settings

## Phase 2 --- Master Data

-   Company
-   Branches
-   Customers
-   Products
-   HS codes
-   UOM
-   Tax profiles
-   Sale types
-   Reference data

## Phase 3 --- Invoice Engine

-   Invoice creation
-   Items
-   Tax engine
-   Validation
-   Numbering
-   Draft workflow
-   PDF

## Phase 4 --- FBR Integration

-   Adapter interface
-   Mock/sandbox adapter
-   Production adapter
-   Payload builder
-   Response parser
-   Error handling
-   Queue
-   Retry
-   Submission center

## Phase 5 --- Compliance/Reporting

-   Credit notes
-   Debit notes
-   Reports
-   Audit
-   Exports

## Phase 6 --- Commercial SaaS

-   Pricing
-   Billing
-   Usage limits
-   API keys
-   Webhooks
-   Onboarding
-   Support

## Phase 7 --- Enterprise

-   SSO
-   ERP/POS integrations
-   Dedicated infrastructure
-   Advanced analytics
-   Partner/reseller portal

------------------------------------------------------------------------

# 56. MVP

### SaaS

-   Registration
-   Login
-   Tenant
-   Users
-   Roles

### Tax

-   Company
-   Branch
-   Customer
-   Product
-   Tax profile
-   Reference data

### Invoicing

-   Create
-   Validate
-   Submit
-   Status
-   PDF
-   QR
-   History

### FBR

-   Adapter
-   Submission center
-   Response handling
-   Errors
-   Retry

### Compliance

-   Credit notes
-   Debit notes
-   Audit
-   Reports

------------------------------------------------------------------------

# 57. V1.5

-   Bulk customer import
-   Bulk product import
-   Excel import/export
-   Multiple branches
-   Advanced dashboard
-   Scheduled reports
-   Email notifications
-   API
-   Webhooks

# 58. V2

-   ERP integration
-   POS integration
-   Accounting integration
-   Advanced analytics
-   PWA
-   Enterprise SSO
-   Advanced billing
-   Partner portal

# 59. V3

-   Multi-country tax architecture
-   Additional tax authorities
-   White-label SaaS
-   Integration marketplace
-   Regional tax adapters

------------------------------------------------------------------------

# 60. Commercial Positioning

Recommended name:

**FBR Invoice Cloud**

Tagline:

**Digital Invoicing. Tax Compliance. Cloud Simplicity.**

Alternative:

**Create. Validate. Submit. Stay Compliant.**

Position it as:

> A professional cloud tax invoicing platform for Pakistani businesses.

Do not market it as FBR itself or as a licensed integrator unless
legally authorized.

------------------------------------------------------------------------

# 61. SaaS Homepage

Hero:

**FBR Digital Invoicing, Simplified.**

Subtitle:

Create professional tax invoices, manage tax data, track FBR submissions
and organize your invoicing operation from one secure cloud platform.

Sections:

1.  Product overview
2.  Invoice workflow
3.  FBR integration
4.  Features
5.  Reports
6.  Security
7.  Pricing
8.  FAQ
9.  Contact

------------------------------------------------------------------------

# 62. Onboarding Journey

``` text
Landing
→ Sign Up
→ Verify Email
→ Organization
→ Taxpayer Setup
→ Branch
→ Integration
→ Reference Data
→ Product
→ Customer
→ First Invoice
→ Dashboard
```

------------------------------------------------------------------------

# 63. Feature Flags

``` text
ENABLE_FBR_PRODUCTION
ENABLE_DEMO_MODE
ENABLE_API
ENABLE_WEBHOOKS
ENABLE_CREDIT_NOTES
ENABLE_DEBIT_NOTES
ENABLE_BULK_IMPORT
ENABLE_ENTERPRISE
```

Use feature flags for staged rollout.

------------------------------------------------------------------------

# 64. Performance Targets

Initial targets:

-   Dashboard API: \< 500 ms typical
-   Master data list: \< 500 ms typical
-   Normal invoice validation: \< 1 second
-   Complex PDF/report generation: asynchronous
-   FBR submission: asynchronous

Do not make users wait indefinitely for an external FBR response.

------------------------------------------------------------------------

# 65. Scalability

Start modular rather than unnecessarily microservice-heavy.

### V1

``` text
Frontend
Backend API
Worker
PostgreSQL
Redis
Object Storage
```

Scale later with:

-   multiple API instances
-   worker pools
-   read replicas
-   reporting database
-   dedicated enterprise infrastructure

------------------------------------------------------------------------

# 66. Three Core Engines

The product should be organized around three independent engines.

``` text
1. SaaS Engine
   Authentication
   Tenants
   Users
   Billing

2. Tax Invoice Engine
   Customers
   Products
   Tax
   Invoices
   Notes
   Reports

3. FBR Integration Engine
   Payload
   Validation
   Submission
   Response
   Retry
   Status
```

This separation is a primary architectural principle.

------------------------------------------------------------------------

# 67. Final Architecture

``` text
USER
 |
Web SaaS
 |
Authentication + Tenant Context
 |
API Gateway
 |
Application API
 |
+-----------------------------+
| Users | Invoice | Tax       |
| FBR   | Reports | Billing   |
+-----------------------------+
 |
Invoice Engine
 |
Validation Engine
 |
FBR Payload Builder
 |
FBR Adapter Layer
 |
Authorized Integration Route
 |
FBR / PRAL
 |
Response
 |
+------------------+
| Submission DB    |
| Audit Log        |
| PDF/Object Store |
+------------------+

Supporting:
PostgreSQL
Redis
Workers
Object Storage
Secrets Manager
Monitoring
Logging
Backups
CI/CD
WAF/CDN
```

------------------------------------------------------------------------

# 68. Production Definition of Done

-   [ ] Registration works
-   [ ] Tenant isolation tested
-   [ ] Company setup works
-   [ ] Branches work
-   [ ] Users and RBAC work
-   [ ] Customers work
-   [ ] Products work
-   [ ] Tax/reference data works
-   [ ] Invoice creation works
-   [ ] Validation works
-   [ ] Approved FBR integration works
-   [ ] FBR responses are stored
-   [ ] Status tracking works
-   [ ] Failed submissions can be corrected/retried
-   [ ] PDF generation works
-   [ ] QR implementation follows current specification
-   [ ] Credit notes work
-   [ ] Debit notes work
-   [ ] Reports work
-   [ ] Audit works
-   [ ] Security testing completed
-   [ ] Backups tested
-   [ ] Monitoring works
-   [ ] Secrets protected
-   [ ] Current FBR requirements verified
-   [ ] Authorized licensed-integrator arrangement confirmed

------------------------------------------------------------------------

# 69. Developer Build Instruction

Build this as a **real production-oriented multi-tenant SaaS**, not a
static demo.

Mandatory rules:

1.  Keep the product separate from CRM.
2.  Use modular architecture.
3.  Isolate FBR logic behind an adapter.
4.  Use PostgreSQL as the system of record.
5.  Enforce tenant isolation server-side.
6.  Use background workers for submissions and long tasks.
7.  Keep complete submission history.
8.  Secure all credentials.
9.  Generate professional PDFs.
10. Implement QR according to the current FBR specification.
11. Include Demo/Mock mode.
12. Separate Development/Sandbox/Staging/Production.
13. Version tax/reference data.
14. Generate invoice numbers transaction-safely.
15. Make submissions idempotent.
16. Support API/webhooks as extensions.
17. Keep billing independent of tax logic.
18. Separate platform-admin from tenant users.
19. Automate tests for tax, security, tenant isolation and FBR
    integration.
20. Verify current FBR requirements immediately before production
    activation.

------------------------------------------------------------------------

# 70. Regulatory Disclaimer

This document is a software architecture/product blueprint, not legal or
tax advice.

FBR legal requirements, APIs, technical specifications, taxpayer
applicability, integration rules, tax rates and reference data may
change.

Before production activation:

1.  Review the latest FBR legal provisions.
2.  Review the latest technical/API documentation.
3.  Confirm taxpayer scenario.
4.  Confirm the licensed-integrator arrangement.
5.  Validate the payload against the current specification.
6.  Test with the authorized integration party.
7.  Obtain professional tax/legal review where required.

FBR's current documentation and the authorized integration arrangement
must remain the production source of truth.
