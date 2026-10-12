import { apiFetch } from './client';
import { CreditNote, DebitNote, NoteReconciliation } from '../types';

export const notesApi = {
  // Credit Notes
  getCreditNotes: async (): Promise<CreditNote[]> => {
    return apiFetch<CreditNote[]>('/notes/credit-notes');
  },

  getCreditNote: async (id: string): Promise<CreditNote> => {
    return apiFetch<CreditNote>(`/notes/credit-notes/${id}`);
  },

  createCreditNote: async (payload: {
    original_invoice_id: string;
    reason: string;
    branch_id?: string;
    taxable_amount: number;
    sales_tax: number;
    extra_tax?: number;
    further_tax?: number;
    auto_submit?: boolean;
  }): Promise<CreditNote> => {
    return apiFetch<CreditNote>('/notes/credit-notes', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  queueSubmitCreditNote: async (id: string, scenario: string = 'AUTO'): Promise<any> => {
    return apiFetch(`/notes/credit-notes/${id}/queue-submit?scenario=${encodeURIComponent(scenario)}`, {
      method: 'POST',
    });
  },

  triggerCreditNotePdfDownload: async (id: string): Promise<void> => {
    const data = await apiFetch<{ document: any; download_url: string; expires_at: string }>(`/notes/credit-notes/${id}/pdf`);
    if (data?.download_url) {
      window.open(data.download_url, '_blank');
    }
  },

  getReconciliation: async (invoiceId: string): Promise<NoteReconciliation> => {
    return apiFetch<NoteReconciliation>(`/notes/credit-notes/reconciliation/${invoiceId}`);
  },

  // Debit Notes
  getDebitNotes: async (): Promise<DebitNote[]> => {
    return apiFetch<DebitNote[]>('/notes/debit-notes');
  },

  getDebitNote: async (id: string): Promise<DebitNote> => {
    return apiFetch<DebitNote>(`/notes/debit-notes/${id}`);
  },

  createDebitNote: async (payload: {
    original_invoice_id: string;
    reason: string;
    branch_id?: string;
    taxable_amount: number;
    sales_tax: number;
    extra_tax?: number;
    further_tax?: number;
    auto_submit?: boolean;
  }): Promise<DebitNote> => {
    return apiFetch<DebitNote>('/notes/debit-notes', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  queueSubmitDebitNote: async (id: string, scenario: string = 'AUTO'): Promise<any> => {
    return apiFetch(`/notes/debit-notes/${id}/queue-submit?scenario=${encodeURIComponent(scenario)}`, {
      method: 'POST',
    });
  },

  triggerDebitNotePdfDownload: async (id: string): Promise<void> => {
    const data = await apiFetch<{ document: any; download_url: string; expires_at: string }>(`/notes/debit-notes/${id}/pdf`);
    if (data?.download_url) {
      window.open(data.download_url, '_blank');
    }
  },
};
