import { apiFetch } from './client';
import { Customer, Product, Branch, Organization, DashboardKPIs } from '../types';

export const masterApi = {
  getCustomers: async (search?: string): Promise<Customer[]> => {
    const qs = search ? `?search=${encodeURIComponent(search)}` : '';
    return apiFetch<Customer[]>(`/customers${qs}`);
  },

  createCustomer: async (payload: Partial<Customer>): Promise<Customer> => {
    return apiFetch<Customer>('/customers', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getProducts: async (search?: string): Promise<Product[]> => {
    const qs = search ? `?search=${encodeURIComponent(search)}` : '';
    return apiFetch<Product[]>(`/products${qs}`);
  },

  createProduct: async (payload: Partial<Product>): Promise<Product> => {
    return apiFetch<Product>('/products', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getBranches: async (): Promise<Branch[]> => {
    return apiFetch<Branch[]>('/branches');
  },

  getTaxRates: async (): Promise<any[]> => {
    return apiFetch('/tax/rates');
  },

  getHSCodes: async (search?: string): Promise<any[]> => {
    const qs = search ? `?search=${encodeURIComponent(search)}` : '';
    return apiFetch(`/tax/hs-codes${qs}`);
  },

  getUOMs: async (): Promise<any[]> => {
    return apiFetch('/tax/uoms');
  },

  getOrganization: async (): Promise<Organization> => {
    return apiFetch<Organization>('/organization');
  },

  updateSettings: async (settings: any): Promise<any> => {
    return apiFetch('/organization/settings', {
      method: 'PATCH',
      body: JSON.stringify(settings),
    });
  },

  getDashboardKPIs: async (): Promise<DashboardKPIs> => {
    return apiFetch<DashboardKPIs>('/reports/dashboard-kpis');
  },

  getAuditLogs: async (): Promise<any[]> => {
    return apiFetch('/audit-logs');
  },
};
