/**
 * Security, Authentication, Tenant, and API Key HTTP API Client.
 */

import { request } from './client';
import {
  ApiKey,
  ApiKeyCreatedResponse,
  AuthTokens,
  LoginResponse,
  Role,
  Tenant,
  User,
} from '../types/security';

export interface LoginPayload {
  email: string;
  password: string;
  tenant_id?: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
  tenant_id?: string;
  roles?: Role[];
}

export interface CreateTenantPayload {
  name: string;
  slug?: string;
  admin_email: string;
  admin_password: string;
  admin_full_name: string;
  quotas?: {
    max_workflows?: number;
    max_daily_executions?: number;
    max_concurrent_simulations?: number;
    max_api_keys?: number;
    rate_limit_rps?: number;
    rate_limit_burst?: number;
  };
}

export interface CreateApiKeyPayload {
  name: string;
  roles?: Role[];
  rate_limit_rps?: number;
  expires_in_days?: number;
}

export interface CreateTenantUserPayload {
  email: string;
  password: string;
  full_name: string;
  roles?: Role[];
}

export const authApi = {
  // Authentication
  login: async (payload: LoginPayload): Promise<LoginResponse> => {
    return request<LoginResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  register: async (payload: RegisterPayload): Promise<LoginResponse> => {
    return request<LoginResponse>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  refreshToken: async (refreshToken: string): Promise<AuthTokens> => {
    return request<AuthTokens>('/api/v1/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  },

  logout: async (refreshToken?: string): Promise<{ message: string }> => {
    return request<{ message: string }>('/api/v1/auth/logout', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  },

  getMe: async (): Promise<User> => {
    return request<User>('/api/v1/auth/me');
  },

  // Tenants
  listTenants: async (): Promise<Tenant[]> => {
    return request<Tenant[]>('/api/v1/tenants');
  },

  getTenant: async (tenantId: string): Promise<Tenant> => {
    return request<Tenant>(`/api/v1/tenants/${tenantId}`);
  },

  createTenant: async (payload: CreateTenantPayload): Promise<Tenant> => {
    return request<Tenant>('/api/v1/tenants', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  listTenantUsers: async (tenantId: string): Promise<User[]> => {
    return request<User[]>(`/api/v1/tenants/${tenantId}/users`);
  },

  createTenantUser: async (tenantId: string, payload: CreateTenantUserPayload): Promise<User> => {
    return request<User>(`/api/v1/tenants/${tenantId}/users`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // API Keys
  listApiKeys: async (): Promise<ApiKey[]> => {
    return request<ApiKey[]>('/api/v1/api-keys');
  },

  createApiKey: async (payload: CreateApiKeyPayload): Promise<ApiKeyCreatedResponse> => {
    return request<ApiKeyCreatedResponse>('/api/v1/api-keys', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  revokeApiKey: async (keyId: string): Promise<{ message: string }> => {
    return request<{ message: string }>(`/api/v1/api-keys/${keyId}`, {
      method: 'DELETE',
    });
  },
};
