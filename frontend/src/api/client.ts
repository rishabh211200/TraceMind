/**
 * Core HTTP client for TraceMind with RFC 7807 problem details error handling,
 * RS256 JWT Authorization, and X-Tenant-Id context propagation.
 */

import { ApiError } from '../types/api';

export const TOKEN_STORAGE_KEY = 'tracemind_access_token';
export const REFRESH_TOKEN_STORAGE_KEY = 'tracemind_refresh_token';
export const TENANT_STORAGE_KEY = 'tracemind_active_tenant';

export class ApiException extends Error {
  public apiError: ApiError;

  constructor(apiError: ApiError) {
    super(apiError.detail || apiError.title || 'An API error occurred');
    this.name = 'ApiException';
    this.apiError = apiError;
  }
}

export function getStoredAccessToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
}

export function getStoredTenantId(): string | null {
  return localStorage.getItem(TENANT_STORAGE_KEY);
}

export function setStoredAuth(accessToken: string, refreshToken?: string, tenantId?: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, refreshToken);
  }
  if (tenantId) {
    localStorage.setItem(TENANT_STORAGE_KEY, tenantId);
  }
}

export function clearStoredAuth(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
  localStorage.removeItem(TENANT_STORAGE_KEY);
}

export async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

  const token = getStoredAccessToken();
  const tenantId = getStoredTenantId();

  const authHeaders: Record<string, string> = {};
  if (token) {
    authHeaders['Authorization'] = `Bearer ${token}`;
  }
  if (tenantId) {
    authHeaders['X-Tenant-Id'] = tenantId;
  }

  const headers = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...authHeaders,
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorPayload: ApiError;
      try {
        errorPayload = await response.json();
      } catch {
        errorPayload = {
          title: response.statusText || 'HTTP Error',
          status: response.status,
          detail: `Request failed with status code ${response.status}`,
        };
      }
      throw new ApiException(errorPayload);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (err) {
    if (err instanceof ApiException) {
      throw err;
    }
    // Network or client-side fetch error
    throw new ApiException({
      title: 'Network Error',
      status: 0,
      detail: err instanceof Error ? err.message : 'Failed to connect to TraceMind API',
    });
  }
}

export function buildQueryString(params: Record<string, unknown>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, String(value));
    }
  }
  const qs = searchParams.toString();
  return qs ? `?${qs}` : '';
}

