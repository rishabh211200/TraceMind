/**
 * Common API pagination, metadata, and RFC 7807 error types.
 */

export interface PaginationMeta {
  total_count: number;
  page: number;
  limit: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  pagination: PaginationMeta;
}

export interface ApiErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ApiError {
  title: string;
  status: number;
  detail: string;
  instance?: string;
  error_code?: string;
  invalid_params?: ApiErrorDetail[];
}
