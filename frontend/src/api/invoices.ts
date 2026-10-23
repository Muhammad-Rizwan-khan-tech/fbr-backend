import { apiFetch } from './client';
import { Invoice, FBRSubmission, BatchSubmissionJob } from '../types';

export const invoicesApi = {
  getInvoices: async (params?: {
    search?: string;
    status?: string;
    fbr_status?: string;
    branch_id?: string;
  }): Promise<Invoice[]> => {
    const query = new URLSearchParams();
    if (params?.search) query.append('search', params.search);
    if (params?.status) query.append('status', params.status);
    if (params?.fbr_status) query.append('fbr_status', params.fbr_status);
    if (params?.branch_id) query.append('branch_id', params.branch_id);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return apiFetch<Invoice[]>(`/invoices${qs}`);
  },

  getInvoice: async (id: string): Promise<Invoice> => {
    return apiFetch<Invoice>(`/invoices/${id}`);
  },

  createInvoice: async (payload: any): Promise<Invoice> => {
    return apiFetch<Invoice>('/invoices', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  validateInvoice: async (id: string): Promise<{ is_valid: boolean; errors: string[]; warnings: string[]; fbr_ready: boolean }> => {
    return apiFetch(`/invoices/${id}/validate`, {
      method: 'POST',
    });
  },

  validateWithFBR: async (id: string): Promise<{
    success: boolean;
    status: string;
    error_code?: string | null;
    error_message?: string | null;
    environment: string;
    official_validation_passed: boolean;
    invoice_submitted: false;
    diagnostics?: Record<string, string | number>;
  }> => {
    return apiFetch(`/invoices/${id}/fbr-validate`, { method: 'POST' });
  },

  submitToFBR: async (id: string, scenario: string = 'AUTO'): Promise<FBRSubmission> => {
    return apiFetch<FBRSubmission>(`/invoices/${id}/submit?scenario=${encodeURIComponent(scenario)}`, {
      method: 'POST',
    });
  },

  queueSubmitToFBR: async (id: string, scenario: string = 'AUTO', idempotencyKey?: string): Promise<any> => {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    return apiFetch(`/invoices/${id}/queue-submit?scenario=${encodeURIComponent(scenario)}`, {
      method: 'POST',
      headers,
    });
  },

  getSubmissionJobs: async (id: string): Promise<any[]> => {
    return apiFetch<any[]>(`/invoices/${id}/jobs`);
  },

  getInvoicePdf: async (id: string): Promise<{ document: any; download_url: string; expires_at: string }> => {
    return apiFetch(`/invoices/${id}/pdf`);
  },

  triggerPdfDownload: async (id: string): Promise<void> => {
    const data = await apiFetch<{ document: any; download_url: string; expires_at: string }>(`/invoices/${id}/pdf`);
    if (data?.download_url) {
      window.open(data.download_url, '_blank');
    }
  },

  getQRImageUrl: (id: string): string => {
    return `/api/v1/invoices/${id}/qr`;
  },

  batchSubmitInvoices: async (invoiceIds: string[], scenario: string = 'AUTO'): Promise<{
    message: string;
    total_requested: number;
    queued_count: number;
    already_accepted_count: number;
    batch_job_id?: string;
    queued_jobs: any[];
  }> => {
    return apiFetch('/invoices/batch-submit', {
      method: 'POST',
      body: JSON.stringify({
        invoice_ids: invoiceIds,
        scenario,
      }),
    });
  },

  getBatchJobStatus: async (jobId: string): Promise<BatchSubmissionJob> => {
    return apiFetch<BatchSubmissionJob>(`/invoices/batch-jobs/${jobId}`);
  },

  reconcileFbrInvoices: async (invoiceIds?: string[]): Promise<{
    total_inspected: number;
    matched_accepted: number;
    marked_failed: number;
    already_valid: number;
    details: any[];
  }> => {
    return apiFetch('/invoices/reconcile-fbr', {
      method: 'POST',
      body: JSON.stringify({
        invoice_ids: invoiceIds,
      }),
    });
  },
};
