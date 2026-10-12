import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types';
import { authApi, LoginResponse } from '../api/auth';

interface AuthContextType {
  user: User | null;
  token: string | null;
  orgName: string;
  login: (credentials: { email: string; pass: string }) => Promise<void>;
  register: (payload: { org_name: string; full_name: string; email: string; password: string; phone?: string; ntn?: string }) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [orgName, setOrgName] = useState<string>(localStorage.getItem('org_name') || 'ABC Distribution Pvt. Ltd.');
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadUser() {
      if (token) {
        try {
          const userData = await authApi.me();
          setUser(userData);
        } catch {
          logout();
        }
      }
      setIsLoading(false);
    }
    loadUser();
  }, [token]);

  const handleAuthSuccess = (res: LoginResponse) => {
    localStorage.setItem('token', res.access_token);
    localStorage.setItem('org_name', res.org_name);
    setToken(res.access_token);
    setOrgName(res.org_name);
    setUser({
      id: res.tenant_id,
      tenant_id: res.tenant_id,
      email: '',
      full_name: res.user_name,
      role: res.role as any,
      is_active: true
    });
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
    localStorage.removeItem('org_name');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, orgName, login, register, logout, isLoading }}>
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
