import { apiFetch } from './client';
import { User } from '../types';

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: string;
  tenant_id: string;
  user_name: string;
  org_name: string;
  refresh_token?: string;
}

export interface ActivationRedeemPayload {
  activation_key: string;
  device_fingerprint: string;
  device_name?: string;
  os_info?: string;
  app_version?: string;
}

export interface ActivationResponse {
  success: boolean;
  access_token: string;
  refresh_token: string;
  token_type: string;
  device_id: string;
  organization: {
    id: string;
    name: string;
    slug: string;
    status: string;
  };
  license: {
    id: string;
    license_number: string;
    license_type: string;
    status: string;
    max_devices: number;
  };
  user: {
    id: string;
    email: string;
    full_name: string;
    role: string;
  };
  message?: string;
}

export interface LicenseStatusResponse {
  license_number: string;
  license_type: string;
  status: string;
  is_valid: boolean;
  organization_id: string;
  organization_name: string;
  fbr_mode: string;
  message: string;
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
    return apiFetch<User>('/me');
  },
};

export const activationApi = {
  redeem: async (payload: ActivationRedeemPayload): Promise<ActivationResponse> => {
    return apiFetch<ActivationResponse>('/activation/redeem', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getLicenseStatus: async (): Promise<LicenseStatusResponse> => {
    return apiFetch<LicenseStatusResponse>('/license/status');
  },

  getCurrentOrganization: async (): Promise<any> => {
    return apiFetch<any>('/organizations/current');
  },

  getFBRStatus: async (): Promise<any> => {
    return apiFetch<any>('/fbr/connection/status');
  },
};
