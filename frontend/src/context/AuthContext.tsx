import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types';
import { authApi, activationApi, LoginResponse, ActivationResponse, LicenseStatusResponse } from '../api/auth';
import { getCompleteDeviceInfo } from '../utils/fingerprint';
import { getApiBaseUrl, setApiBaseUrl } from '../api/client';

interface AuthContextType {
  user: User | null;
  token: string | null;
  orgName: string;
  isActivated: boolean;
  license: LicenseStatusResponse | null;
  isLoading: boolean;
  apiBaseUrl: string;
  activate: (activationKey: string, deviceName?: string) => Promise<ActivationResponse>;
  login: (credentials: { email: string; pass: string }) => Promise<void>;
  register: (payload: { org_name: string; full_name: string; email: string; password: string; phone?: string; ntn?: string }) => Promise<void>;
  logout: () => void;
  updateApiEndpoint: (url: string) => void;
  refreshLicenseStatus: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [orgName, setOrgName] = useState<string>(localStorage.getItem('org_name') || 'ABC Distribution Pvt. Ltd.');
  const [license, setLicense] = useState<LicenseStatusResponse | null>(null);
  const [isActivated, setIsActivated] = useState<boolean>(() => {
    return localStorage.getItem('is_activated') === 'true' || !!localStorage.getItem('token');
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [apiBaseUrl, setApiBaseUrlState] = useState<string>(getApiBaseUrl());

  const refreshLicenseStatus = async () => {
    try {
      const lic = await activationApi.getLicenseStatus();
      setLicense(lic);
      if (lic.is_valid) {
        setIsActivated(true);
        localStorage.setItem('is_activated', 'true');
      }
    } catch {
      // Ignore license check error
    }
  };

  useEffect(() => {
    async function restoreSession() {
      if (token) {
        try {
          // Fetch current user and verify token
          const userData = await authApi.me();
          setUser(userData);
          setIsActivated(true);
          localStorage.setItem('is_activated', 'true');

          // Check live permanent license standing
          await refreshLicenseStatus();
        } catch {
          logout();
        }
      }
      setIsLoading(false);
    }
    restoreSession();
  }, [token]);

  const handleActivationSuccess = (res: ActivationResponse) => {
    localStorage.setItem('token', res.access_token);
    localStorage.setItem('refresh_token', res.refresh_token);
    localStorage.setItem('org_name', res.organization.name);
    localStorage.setItem('tenant_id', res.organization.id);
    localStorage.setItem('is_activated', 'true');

    setToken(res.access_token);
    setOrgName(res.organization.name);
    setIsActivated(true);
    setUser({
      id: res.user.id,
      tenant_id: res.organization.id,
      email: res.user.email,
      full_name: res.user.full_name,
      role: res.user.role as any,
      is_active: true,
    });
    setLicense({
      license_number: res.license.license_number,
      license_type: res.license.license_type,
      status: res.license.status,
      is_valid: res.license.status === 'ACTIVE',
      organization_id: res.organization.id,
      organization_name: res.organization.name,
      fbr_mode: 'DEMO',
      message: 'Permanent license active.',
    });
  };

  const activate = async (activationKey: string, customDeviceName?: string): Promise<ActivationResponse> => {
    const devInfo = await getCompleteDeviceInfo();
    if (customDeviceName && customDeviceName.trim().length > 0) {
      localStorage.setItem('fbr_device_name', customDeviceName.trim());
      devInfo.deviceName = customDeviceName.trim();
    }

    const res = await activationApi.redeem({
      activation_key: activationKey.trim(),
      device_fingerprint: devInfo.fingerprint,
      device_name: devInfo.deviceName,
      os_info: devInfo.osInfo,
      app_version: devInfo.appVersion,
    });

    handleActivationSuccess(res);
    return res;
  };

  const handleAuthSuccess = (res: LoginResponse) => {
    localStorage.setItem('token', res.access_token);
    localStorage.setItem('org_name', res.org_name);
    if (res.refresh_token) {
      localStorage.setItem('refresh_token', res.refresh_token);
    }
    setToken(res.access_token);
    setOrgName(res.org_name);
    setIsActivated(true);
    localStorage.setItem('is_activated', 'true');
    setUser({
      id: res.tenant_id,
      tenant_id: res.tenant_id,
      email: '',
      full_name: res.user_name,
      role: res.role as any,
      is_active: true,
    });
    refreshLicenseStatus();
  };

  const login = async ({ email, pass }: { email: string; pass: string }) => {
    const res = await authApi.login(email, pass);
    handleAuthSuccess(res);
  };

  const register = async (payload: { org_name: string; full_name: string; email: string; password: string; phone?: string; ntn?: string }) => {
    const res = await authApi.register(payload);
    handleAuthSuccess(res);
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
    setLicense(null);
  };

  const updateApiEndpoint = (url: string) => {
    setApiBaseUrl(url);
    setApiBaseUrlState(getApiBaseUrl());
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        orgName,
        isActivated,
        license,
        isLoading,
        apiBaseUrl,
        activate,
        login,
        register,
        logout,
        updateApiEndpoint,
        refreshLicenseStatus,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
