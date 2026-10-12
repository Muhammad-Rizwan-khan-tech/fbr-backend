import { apiFetch } from './client';
import { FBRSubmission } from '../types';

export interface FBRStatus {
  is_connected: boolean;
  environment: string;
  adapter: string;
  last_successful_submission?: string;
  pending_queue_count: number;
  failed_submissions_count: number;
  total_valid_submissions: number;
}

export const fbrApi = {
  getStatus: async (): Promise<FBRStatus> => {
    return apiFetch<FBRStatus>('/fbr/status');
  },

  getSubmissions: async (status?: string): Promise<FBRSubmission[]> => {
    const qs = status ? `?status=${encodeURIComponent(status)}` : '';
    return apiFetch<FBRSubmission[]>(`/fbr/submissions${qs}`);
  },

  getSubmission: async (id: string): Promise<FBRSubmission> => {
    return apiFetch<FBRSubmission>(`/fbr/submissions/${id}`);
  },

  retrySubmission: async (id: string): Promise<FBRSubmission> => {
    return apiFetch<FBRSubmission>(`/fbr/submissions/${id}/retry`, {
      method: 'POST',
    });
  },

  testConnection: async (): Promise<any> => {
    return apiFetch('/fbr/test-connection', {
      method: 'POST',
    });
  },
};
