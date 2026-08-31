import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  authApi,
  LoginPayload,
  RegisterPayload,
} from '../api/auth';
import {
  clearStoredAuth,
  getStoredAccessToken,
  getStoredRefreshToken,
  getStoredTenantId,
  setStoredAuth,
} from '../api/client';
import {
  AuthTokens,
  Permission,
  Role,
  Tenant,
  User,
} from '../types/security';

interface AuthContextType {
  user: User | null;
  tenant: Tenant | null;
  activeTenantId: string;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  switchTenant: (tenantId: string) => void;
  hasPermission: (permission: Permission) => boolean;
  hasRole: (role: Role) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [activeTenantId, setActiveTenantId] = useState<string>(
    getStoredTenantId() || 'tenant_system'
  );
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Initialize and check current authentication state
  useEffect(() => {
    const initAuth = async () => {
      const accessToken = getStoredAccessToken();
      const refreshToken = getStoredRefreshToken();

      if (!accessToken && !refreshToken) {
        setIsLoading(false);
        return;
      }

      try {
        if (accessToken) {
          const me = await authApi.getMe();
          setUser(me);
          setActiveTenantId(me.tenant_id);
        } else if (refreshToken) {
          const newTokens = await authApi.refreshToken(refreshToken);
          setStoredAuth(newTokens.access_token, newTokens.refresh_token, newTokens.tenant_id);
          setTokens(newTokens);
          setActiveTenantId(newTokens.tenant_id);
          const me = await authApi.getMe();
          setUser(me);
        }
      } catch (err) {
        console.warn('Session expired or invalid, clearing authentication', err);
        clearStoredAuth();
        setUser(null);
        setTokens(null);
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, []);

  const login = async (payload: LoginPayload) => {
    setIsLoading(true);
    try {
      const res = await authApi.login(payload);
      setStoredAuth(res.tokens.access_token, res.tokens.refresh_token, res.tenant.id);
      setTokens(res.tokens);
      setUser(res.user);
      setTenant(res.tenant);
      setActiveTenantId(res.tenant.id);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (payload: RegisterPayload) => {
    setIsLoading(true);
    try {
      const res = await authApi.register(payload);
      setStoredAuth(res.tokens.access_token, res.tokens.refresh_token, res.tenant.id);
      setTokens(res.tokens);
      setUser(res.user);
      setTenant(res.tenant);
      setActiveTenantId(res.tenant.id);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    const refreshToken = getStoredRefreshToken();
    try {
      if (refreshToken) {
        await authApi.logout(refreshToken);
      }
    } catch {
      // Ignore network errors during logout
    } finally {
      clearStoredAuth();
      setUser(null);
      setTenant(null);
      setTokens(null);
      setActiveTenantId('tenant_system');
    }
  };

  const switchTenant = (tenantId: string) => {
    setActiveTenantId(tenantId);
    setStoredAuth(getStoredAccessToken() || '', getStoredRefreshToken() || '', tenantId);
  };

  const hasPermission = (permission: Permission): boolean => {
    if (!user) return false;
    if (user.roles.includes('platform_admin')) return true;
    if (tokens?.permissions?.includes(permission)) return true;
    return false;
  };

  const hasRole = (role: Role): boolean => {
    if (!user) return false;
    return user.roles.includes(role);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        tenant,
        activeTenantId,
        tokens,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        switchTenant,
        hasPermission,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
