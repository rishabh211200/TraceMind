/**
 * Core HTTP client for TraceMind with RFC 7807 problem details error handling.
 */

import { ApiError } from '../types/api';

export class ApiException extends Error {
  public apiError: ApiError;

  constructor(apiError: ApiError) {
    super(apiError.detail || apiError.title || 'An API error occurred');
    this.name = 'ApiException';
    this.apiError = apiError;
  }
}

export async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

  const headers = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
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
