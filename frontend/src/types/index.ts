export interface User {
  id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  role: 'SUPER_ADMIN' | 'ORG_ADMIN' | 'INVOICE_OPERATOR' | 'TAX_OFFICER' | 'ACCOUNTANT' | 'VIEWER';
  phone?: string;
  is_active: boolean;
}

export interface OrganizationSettings {
  id: string;
  organization_id: string;
  invoice_prefix: string;
  next_invoice_number: number;
  credit_note_prefix: string;
  debit_note_prefix: string;
  default_terms?: string;
  fbr_mode: 'DEMO' | 'SANDBOX' | 'PRODUCTION';
  enable_auto_submit: boolean;
  fbr_pos_id?: string;
  fbr_api_token?: string;
  fbr_base_url?: string;
}

export interface Taxpayer {
  id: string;
  tenant_id: string;
  legal_name: string;
  trade_name?: string;
  ntn: string;
  strn?: string;
  registration_type: string;
  business_type: string;
  address: string;
  city: string;
  province: string;
  postal_code?: string;
  country: string;
  phone?: string;
  email?: string;
  website?: string;
  authorized_signatory_name?: string;
  authorized_signatory_designation?: string;
}

export interface Branch {
  id: string;
  tenant_id: string;
  branch_name: string;
  branch_code: string;
  fbr_pos_id?: string;
  address: string;
  city: string;
  province: string;
  phone?: string;
  email?: string;
  is_active: boolean;
  is_main: boolean;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  plan: string;
  status: string;
  is_active: boolean;
  settings?: OrganizationSettings;
  taxpayer?: Taxpayer;
  branches: Branch[];
}

export interface Customer {
  id: string;
  tenant_id: string;
  name: string;
  ntn?: string;
  strn?: string;
  cnic?: string;
  registration_type: string;
  buyer_type: string;
  address: string;
  city: string;
  province: string;
  phone?: string;
  email?: string;
  buyer_reference?: string;
  is_active: boolean;
}

export interface Product {
  id: string;
  tenant_id: string;
  item_code: string;
  name: string;
  description?: string;
  hs_code: string;
  uom: string;
  sale_type: string;
  tax_rate: number;
  sro_reference?: string;
  unit_price: number;
  is_active: boolean;
}

export interface InvoiceItem {
  id?: string;
  product_id?: string;
  item_seq?: number;
  item_code: string;
  description: string;
  hs_code: string;
  quantity: number;
  uom: string;
  unit_price: number;
  gross_amount?: number;
  discount: number;
  taxable_amount?: number;
  tax_rate: number;
  tax_amount?: number;
  line_total?: number;
  sale_type: string;
  sro_reference?: string;
}

export interface Invoice {
  id: string;
  tenant_id: string;
  branch_id: string;
  customer_id: string;
  invoice_number: string;
  invoice_type: string;
  invoice_date: string;
  due_date?: string;
  seller_name: string;
  seller_ntn: string;
  seller_strn?: string;
  seller_branch_code: string;
  seller_province: string;
  buyer_name: string;
  buyer_ntn?: string;
  buyer_strn?: string;
  buyer_cnic?: string;
  buyer_registration_type: string;
  buyer_address: string;
  buyer_province: string;
  subtotal: number;
  total_discount: number;
  taxable_amount: number;
  total_tax: number;
  other_charges: number;
  grand_total: number;
  status: 'DRAFT' | 'VALIDATING' | 'INVALID' | 'READY' | 'QUEUED' | 'SUBMITTING' | 'RETRYING' | 'SUBMITTED' | 'VALID' | 'REJECTED' | 'FAILED' | 'CANCELLED';
  fbr_status: 'NOT_SUBMITTED' | 'PENDING' | 'VALID' | 'INVALID' | 'FAILED';
  fbr_invoice_number?: string;
  fbr_qr_data?: string;
  fbr_submission_date?: string;
  fbr_error_code?: string;
  fbr_error_message?: string;
  fbr_environment?: string;
  fbr_provider?: string;
  fbr_is_simulated?: boolean;
  reference_number?: string;
  notes?: string;
  correlation_id?: string;
  items: InvoiceItem[];
}

export interface InvoiceSubmissionJob {
  id: string;
  invoice_id: string;
  parent_job_id?: string;
  environment: string;
  provider: string;
  is_simulated: boolean;
  demo_scenario?: string;
  status: 'QUEUED' | 'PROCESSING' | 'SUBMITTED' | 'ACCEPTED' | 'REJECTED' | 'RETRYING' | 'FAILED';
  attempt_count: number;
  max_attempts: number;
  next_retry_at?: string;
  enqueued_at?: string;
  started_at?: string;
  completed_at?: string;
  last_error_code?: string;
  last_error_message?: string;
  fbr_reference?: string;
  correlation_id: string;
  idempotency_key?: string;
  created_at: string;
}

export interface DocumentRecord {
  id: string;
  tenant_id: string;
  document_type: string;
  entity_type: string;
  entity_id: string;
  storage_provider: string;
  file_name: string;
  mime_type: string;
  file_size: number;
  checksum: string;
  version: number;
  is_simulated: boolean;
  created_at: string;
}

export interface DocumentDownload {
  document: DocumentRecord;
  download_url: string;
  expires_at: string;
}

export interface AppNotification {
  id: string;
  tenant_id: string;
  user_id: string;
  event_type: string;
  severity: 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR';
  title: string;
  message: string;
  entity_type?: string;
  entity_id?: string;
  is_read: boolean;
  read_at?: string;
  correlation_id?: string;
  created_at: string;
}

export interface FBRSubmissionAttempt {
  id: string;
  attempt_number: number;
  http_status_code?: number;
  status: string;
  error_message?: string;
  latency_ms: number;
  created_at: string;
}

export interface FBRSubmission {
  id: string;
  invoice_id: string;
  environment: string;
  adapter_name: string;
  request_id: string;
  correlation_id?: string;
  status: string;
  fbr_invoice_number?: string;
  fbr_reference?: string;
  qr_code_data?: string;
  retry_count: number;
  is_retryable: boolean;
  error_code?: string;
  error_message?: string;
  gateway_diagnostics?: {
    http_status?: number;
    content_type?: string;
    response_kind?: string;
    body_chars?: number;
    body_sha256_prefix?: string;
    array_items?: number;
  };
  submitted_at: string;
  responded_at?: string;
  attempts: FBRSubmissionAttempt[];
}

export interface DashboardKPIs {
  today_invoices_count: number;
  monthly_invoices_count: number;
  valid_fbr_count: number;
  pending_submissions_count: number;
  failed_submissions_count: number;
  total_taxable_amount: number;
  total_tax: number;
  total_grand_amount: number;
  credit_notes_count: number;
  debit_notes_count: number;
}

export interface CreditNote {
  id: string;
  tenant_id: string;
  branch_id?: string;
  original_invoice_id: string;
  note_number: string;
  note_date: string;
  reason: string;
  taxable_amount: number;
  sales_tax: number;
  extra_tax: number;
  further_tax: number;
  total_tax: number;
  grand_total: number;
  status: 'DRAFT' | 'ISSUED' | 'POSTED' | 'CANCELLED';
  fbr_invoice_number?: string;
  fbr_qr_data?: string;
  fbr_submission_date?: string;
  fbr_environment?: string;
  fbr_provider?: string;
  fbr_is_simulated?: boolean;
  correlation_id?: string;
  created_at: string;
}

export interface DebitNote {
  id: string;
  tenant_id: string;
  branch_id?: string;
  original_invoice_id: string;
  note_number: string;
  note_date: string;
  reason: string;
  taxable_amount: number;
  sales_tax: number;
  extra_tax: number;
  further_tax: number;
  total_tax: number;
  grand_total: number;
  status: 'DRAFT' | 'ISSUED' | 'POSTED' | 'CANCELLED';
  fbr_invoice_number?: string;
  fbr_qr_data?: string;
  fbr_submission_date?: string;
  fbr_environment?: string;
  fbr_provider?: string;
  fbr_is_simulated?: boolean;
  correlation_id?: string;
  created_at: string;
}

export interface NoteReconciliation {
  invoice_id: string;
  invoice_number: string;
  invoice_grand_total: number;
  total_previously_credited: number;
  remaining_creditable_amount: number;
  credit_notes: Array<{
    id: string;
    note_number: string;
    grand_total: number;
    reason: string;
    status: string;
    fbr_invoice_number?: string;
    created_at: string;
  }>;
}

export interface BatchJobItem {
  invoice_id: string;
  submission_job_id?: string;
  status: string;
  error?: string;
  fbr_invoice_number?: string;
}

export interface BatchSubmissionJob {
  job_id: string;
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED';
  total_items: number;
  processed_items: number;
  successful_items: number;
  failed_items: number;
  enqueued_at: string;
  started_at?: string;
  completed_at?: string;
  items: BatchJobItem[];
}
