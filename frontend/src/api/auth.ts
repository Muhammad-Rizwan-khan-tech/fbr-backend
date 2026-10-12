import { apiFetch } from './client';
import { User } from '../types';

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: string;
  tenant_id: string;
  user_name: string;
  org_name: string;
}

export const authApi = {
  login: async (email: string, password: string): Promise<LoginResponse> => {
    return apiFetch<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  register: async (payload: {
    org_name: string;
    full_name: string;
    email: string;
    password: string;
    phone?: string;
    ntn?: string;
  }): Promise<LoginResponse> => {
    return apiFetch<LoginResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  me: async (): Promise<User> => {
    return apiFetch<User>('/auth/me');
  },
};
