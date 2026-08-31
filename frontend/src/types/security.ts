export type Role =
  | 'platform_admin'
  | 'tenant_admin'
  | 'operator'
  | 'analyst'
  | 'viewer';

export type Permission =
  | 'workflows:read'
  | 'workflows:write'
  | 'traces:read'
  | 'predictions:read'
  | 'predictions:execute'
  | 'anomalies:read'
  | 'anomalies:feedback'
  | 'rca:read'
  | 'rca:execute'
  | 'optimizer:read'
  | 'optimizer:execute'
  | 'analyst:read'
  | 'analyst:execute'
  | 'remediation:read'
  | 'remediation:synthesize'
  | 'remediation:execute'
  | 'remediation:rollback'
  | 'remediation:policy_admin'
  | 'audit:read'
  | 'audit:verify'
  | 'simulator:execute'
  | 'chaos:inject'
  | 'services:read'
  | 'services:write'
  | 'incidents:read'
  | 'tenants:read'
  | 'tenants:admin'
  | 'api_keys:manage'
  | 'users:manage';

export interface User {
  id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  roles: Role[];
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface TenantQuotas {
  max_workflows: number;
  max_daily_executions: number;
  max_concurrent_simulations: number;
  max_api_keys: number;
  rate_limit_rps: number;
  rate_limit_burst: number;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  quotas: TenantQuotas;
  created_at: string;
  updated_at: string;
}

export interface ApiKey {
  id: string;
  tenant_id: string;
  user_id: string;
  name: string;
  prefix: string;
  roles: Role[];
  rate_limit_rps: number;
  is_active: boolean;
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
}

export interface ApiKeyCreatedResponse extends ApiKey {
  secret_token: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  tenant_id: string;
  roles: Role[];
  permissions: Permission[];
}

export interface LoginResponse {
  tokens: AuthTokens;
  user: User;
  tenant: Tenant;
}
