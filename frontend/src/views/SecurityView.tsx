import React, { useEffect, useState } from 'react';
import {
  Shield,
  Key,
  Building,
  UserCheck,
  Lock,
  Plus,
  Trash2,
  Copy,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react';
import { authApi, CreateApiKeyPayload, CreateTenantPayload, CreateTenantUserPayload } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import { ApiKey, ApiKeyCreatedResponse, Role, Tenant, User } from '../types/security';

export const SecurityView: React.FC = () => {
  const { user, activeTenantId, hasRole, switchTenant, login, isAuthenticated, logout } = useAuth();

  // Tab selection inside Security View
  const [activeSubTab, setActiveSubTab] = useState<'keys' | 'tenants' | 'users' | 'login'>('keys');

  // API Keys state
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loadingKeys, setLoadingKeys] = useState<boolean>(false);
  const [createdKeySecret, setCreatedKeySecret] = useState<ApiKeyCreatedResponse | null>(null);
  const [showKeyForm, setShowKeyForm] = useState<boolean>(false);
  const [newKeyName, setNewKeyName] = useState<string>('');
  const [newKeyRole, setNewKeyRole] = useState<Role>('viewer');
  const [newKeyRps, setNewKeyRps] = useState<number>(60);
  const [copiedKey, setCopiedKey] = useState<boolean>(false);

  // Tenants state
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loadingTenants, setLoadingTenants] = useState<boolean>(false);
  const [showTenantForm, setShowTenantForm] = useState<boolean>(false);
  const [newTenantName, setNewTenantName] = useState<string>('');
  const [newTenantAdminEmail, setNewTenantAdminEmail] = useState<string>('');
  const [newTenantAdminPassword, setNewTenantAdminPassword] = useState<string>('');
  const [newTenantAdminName, setNewTenantAdminName] = useState<string>('');

  // Users state
  const [tenantUsers, setTenantUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState<boolean>(false);
  const [showUserForm, setShowUserForm] = useState<boolean>(false);
  const [newUserEmail, setNewUserEmail] = useState<string>('');
  const [newUserPassword, setNewUserPassword] = useState<string>('');
  const [newUserFullName, setNewUserFullName] = useState<string>('');
  const [newUserRole, setNewUserRole] = useState<Role>('viewer');

  // Auth form state (if not logged in)
  const [loginEmail, setLoginEmail] = useState<string>('admin@tracemind.io');
  const [loginPassword, setLoginPassword] = useState<string>('TraceMind#Admin2026!');
  const [authError, setAuthError] = useState<string | null>(null);
  const [authSubmitting, setAuthSubmitting] = useState<boolean>(false);

  // Fetch API keys
  const loadApiKeys = async () => {
    if (!isAuthenticated) return;
    setLoadingKeys(true);
    try {
      const keys = await authApi.listApiKeys();
      setApiKeys(keys);
    } catch (err) {
      console.error('Failed to load API keys', err);
    } finally {
      setLoadingKeys(false);
    }
  };

  // Fetch tenants
  const loadTenants = async () => {
    if (!isAuthenticated) return;
    setLoadingTenants(true);
    try {
      const list = await authApi.listTenants();
      setTenants(list);
    } catch (err) {
      console.error('Failed to load tenants', err);
    } finally {
      setLoadingTenants(false);
    }
  };

  // Fetch users for active tenant
  const loadTenantUsers = async () => {
    if (!isAuthenticated || !activeTenantId) return;
    setLoadingUsers(true);
    try {
      const users = await authApi.listTenantUsers(activeTenantId);
      setTenantUsers(users);
    } catch (err) {
      console.error('Failed to load tenant users', err);
    } finally {
      setLoadingUsers(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      loadApiKeys();
      loadTenants();
      loadTenantUsers();
    }
  }, [isAuthenticated, activeTenantId]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthSubmitting(true);
    setAuthError(null);
    try {
      await login({ email: loginEmail, password: loginPassword });
    } catch (err: any) {
      setAuthError(err?.message || 'Authentication failed. Verify your email and password.');
    } finally {
      setAuthSubmitting(false);
    }
  };

  const handleCreateApiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: CreateApiKeyPayload = {
        name: newKeyName,
        roles: [newKeyRole],
        rate_limit_rps: Number(newKeyRps),
      };
      const res = await authApi.createApiKey(payload);
      setCreatedKeySecret(res);
      setShowKeyForm(false);
      setNewKeyName('');
      loadApiKeys();
    } catch (err: any) {
      alert(`Failed to create API key: ${err?.message || err}`);
    }
  };

  const handleRevokeApiKey = async (keyId: string) => {
    if (!confirm('Are you sure you want to revoke this API key? This action is immediate and irrevocable.')) {
      return;
    }
    try {
      await authApi.revokeApiKey(keyId);
      loadApiKeys();
    } catch (err: any) {
      alert(`Failed to revoke API key: ${err?.message || err}`);
    }
  };

  const handleCreateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: CreateTenantPayload = {
        name: newTenantName,
        admin_email: newTenantAdminEmail,
        admin_password: newTenantAdminPassword,
        admin_full_name: newTenantAdminName,
      };
      await authApi.createTenant(payload);
      setShowTenantForm(false);
      setNewTenantName('');
      setNewTenantAdminEmail('');
      setNewTenantAdminPassword('');
      setNewTenantAdminName('');
      loadTenants();
    } catch (err: any) {
      alert(`Failed to create tenant: ${err?.message || err}`);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: CreateTenantUserPayload = {
        email: newUserEmail,
        password: newUserPassword,
        full_name: newUserFullName,
        roles: [newUserRole],
      };
      await authApi.createTenantUser(activeTenantId, payload);
      setShowUserForm(false);
      setNewUserEmail('');
      setNewUserPassword('');
      setNewUserFullName('');
      loadTenantUsers();
    } catch (err: any) {
      alert(`Failed to create user: ${err?.message || err}`);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2500);
  };

  return (
    <div className="space-y-6">
      {/* View Title & Status Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-slate-900/60 p-5 rounded-2xl border border-slate-800 backdrop-blur-md">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
              <Shield className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-100 font-mono flex items-center gap-2">
                Enterprise Zero-Trust Security & Multi-Tenancy
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono border border-emerald-500/30">
                  RS256 &bull; Argon2id &bull; AES-256-GCM
                </span>
              </h1>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Role-Based Access Control, tenant boundaries, cryptographic secret envelopes & API key governance
              </p>
            </div>
          </div>
        </div>

        {/* Tenant Switcher & Auth Status */}
        <div className="flex items-center gap-3">
          {isAuthenticated ? (
            <div className="flex items-center gap-2">
              <div className="px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700 text-xs font-mono flex items-center gap-2">
                <Building className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-slate-400">Tenant:</span>
                <span className="text-emerald-300 font-semibold">{activeTenantId}</span>
              </div>
              <div className="px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700 text-xs font-mono flex items-center gap-2">
                <UserCheck className="h-3.5 w-3.5 text-cyan-400" />
                <span className="text-slate-200">{user?.full_name || user?.email}</span>
                <span className="text-[10px] px-1.5 py-0.2 bg-cyan-500/20 text-cyan-300 rounded border border-cyan-500/30">
                  {user?.roles[0]}
                </span>
              </div>
              <button
                onClick={logout}
                className="px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 text-xs font-mono transition"
              >
                Logout
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-amber-400 flex items-center gap-1.5 bg-amber-500/10 px-3 py-1.5 rounded-lg border border-amber-500/20">
                <AlertTriangle className="h-3.5 w-3.5" /> Authentication Required
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Unauthenticated Login Screen */}
      {!isAuthenticated ? (
        <div className="max-w-md mx-auto bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl backdrop-blur-md">
          <div className="text-center mb-6">
            <div className="inline-flex p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 mb-3">
              <Lock className="h-8 w-8" />
            </div>
            <h2 className="text-lg font-bold text-slate-100 font-mono">Sign In to TraceMind</h2>
            <p className="text-xs text-slate-400 font-mono mt-1">
              Zero-trust RS256 token issuance and RBAC session initialization
            </p>
          </div>

          {authError && (
            <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono">
              {authError}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-mono text-slate-400 mb-1">Email Address</label>
              <input
                type="email"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                required
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm font-mono text-slate-100 focus:outline-none focus:border-emerald-500/60"
              />
            </div>
            <div>
              <label className="block text-xs font-mono text-slate-400 mb-1">Password</label>
              <input
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                required
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm font-mono text-slate-100 focus:outline-none focus:border-emerald-500/60"
              />
            </div>

            <button
              type="submit"
              disabled={authSubmitting}
              className="w-full py-2.5 px-4 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold font-mono text-xs uppercase tracking-wider transition shadow-lg shadow-emerald-500/20 disabled:opacity-50"
            >
              {authSubmitting ? 'Authenticating...' : 'Sign In with Zero-Trust JWT'}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-slate-800/80 text-[11px] font-mono text-slate-500 space-y-1">
            <div>Default System Admin: <span className="text-slate-400">admin@tracemind.io</span></div>
            <div>Default Password: <span className="text-slate-400">TraceMind#Admin2026!</span></div>
          </div>
        </div>
      ) : (
        /* Authenticated Security Dashboard */
        <div className="space-y-6">
          {/* Navigation Sub-Tabs */}
          <div className="flex items-center gap-2 border-b border-slate-800/80 pb-2 font-mono text-xs">
            <button
              onClick={() => setActiveSubTab('keys')}
              className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition ${
                activeSubTab === 'keys'
                  ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Key className="h-3.5 w-3.5" /> API Keys ({apiKeys.length})
            </button>
            <button
              onClick={() => setActiveSubTab('tenants')}
              className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition ${
                activeSubTab === 'tenants'
                  ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Building className="h-3.5 w-3.5" /> Tenant Organizations ({tenants.length})
            </button>
            <button
              onClick={() => setActiveSubTab('users')}
              className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition ${
                activeSubTab === 'users'
                  ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <UserCheck className="h-3.5 w-3.5" /> Tenant Users ({tenantUsers.length})
            </button>
          </div>

          {/* Newly Created Secret Modal / Alert */}
          {createdKeySecret && (
            <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/40 text-slate-100 font-mono space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-amber-300 font-bold text-sm">
                  <AlertTriangle className="h-5 w-5" /> API Key Created — Save This Secret Now!
                </div>
                <button
                  onClick={() => setCreatedKeySecret(null)}
                  className="text-xs text-slate-400 hover:text-slate-200"
                >
                  Dismiss
                </button>
              </div>
              <p className="text-xs text-slate-300">
                This raw secret token will <strong>NEVER</strong> be displayed again. If you lose it, you must generate a new API key.
              </p>
              <div className="flex items-center gap-2 bg-slate-950 p-2.5 rounded-xl border border-amber-500/30">
                <code className="text-xs font-mono text-emerald-400 flex-1 break-all select-all">
                  {createdKeySecret.secret_token}
                </code>
                <button
                  onClick={() => copyToClipboard(createdKeySecret.secret_token)}
                  className="px-3 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 rounded-lg text-xs flex items-center gap-1 shrink-0 transition"
                >
                  {copiedKey ? <CheckCircle className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  {copiedKey ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>
          )}

          {/* Sub-Tab 1: API Keys */}
          {activeSubTab === 'keys' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-200 font-mono">Programmatic API Keys</h3>
                  <p className="text-xs text-slate-400 font-mono">High-entropy cryptographic keys for external pipeline ingestion & CLI actuation</p>
                </div>
                <button
                  onClick={() => setShowKeyForm(!showKeyForm)}
                  className="px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center gap-1.5 transition"
                >
                  <Plus className="h-3.5 w-3.5" /> Generate API Key
                </button>
              </div>

              {/* Create Key Form */}
              {showKeyForm && (
                <form onSubmit={handleCreateApiKey} className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl space-y-4 font-mono">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Key Description / Name</label>
                      <input
                        type="text"
                        value={newKeyName}
                        onChange={(e) => setNewKeyName(e.target.value)}
                        placeholder="e.g., ci-cd-pipeline"
                        required
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Assigned Role</label>
                      <select
                        value={newKeyRole}
                        onChange={(e) => setNewKeyRole(e.target.value as Role)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100"
                      >
                        <option value="viewer">viewer (Read-only)</option>
                        <option value="analyst">analyst (Predictions & RCA)</option>
                        <option value="operator">operator (Remediation & Actuation)</option>
                        <option value="tenant_admin">tenant_admin (Tenant Administration)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Rate Limit (RPS)</label>
                      <input
                        type="number"
                        value={newKeyRps}
                        onChange={(e) => setNewKeyRps(Number(e.target.value))}
                        min={1}
                        max={1000}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100"
                      />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setShowKeyForm(false)}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 text-xs"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-3 py-1.5 rounded-lg bg-emerald-500 text-slate-950 font-bold text-xs"
                    >
                      Generate Key
                    </button>
                  </div>
                </form>
              )}

              {/* API Keys Table */}
              <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
                <table className="w-full text-left border-collapse font-mono text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-950/60 text-slate-400">
                      <th className="py-2.5 px-4 font-semibold">Key Name</th>
                      <th className="py-2.5 px-4 font-semibold">Key Prefix</th>
                      <th className="py-2.5 px-4 font-semibold">Roles</th>
                      <th className="py-2.5 px-4 font-semibold">Rate Limit</th>
                      <th className="py-2.5 px-4 font-semibold">Last Used</th>
                      <th className="py-2.5 px-4 font-semibold">Status</th>
                      <th className="py-2.5 px-4 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {apiKeys.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-6 text-center text-slate-500">
                          {loadingKeys ? 'Loading API keys...' : 'No API keys provisioned for this tenant.'}
                        </td>
                      </tr>
                    ) : (
                      apiKeys.map((k) => (
                        <tr key={k.id} className="hover:bg-slate-800/30 transition">
                          <td className="py-2.5 px-4 font-semibold text-slate-200">{k.name}</td>
                          <td className="py-2.5 px-4 text-emerald-400 font-mono">{k.prefix}...</td>
                          <td className="py-2.5 px-4">
                            <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[10px]">
                              {k.roles.join(', ')}
                            </span>
                          </td>
                          <td className="py-2.5 px-4 text-slate-400">{k.rate_limit_rps} rps</td>
                          <td className="py-2.5 px-4 text-slate-400">{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : 'Never'}</td>
                          <td className="py-2.5 px-4">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] ${k.is_active ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}`}>
                              {k.is_active ? 'ACTIVE' : 'REVOKED'}
                            </span>
                          </td>
                          <td className="py-2.5 px-4 text-right">
                            {k.is_active && (
                              <button
                                onClick={() => handleRevokeApiKey(k.id)}
                                className="p-1 hover:bg-rose-500/20 rounded text-rose-400 transition"
                                title="Revoke API Key"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Sub-Tab 2: Tenant Organizations */}
          {activeSubTab === 'tenants' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-200 font-mono">Tenant Organizations & Quotas</h3>
                  <p className="text-xs text-slate-400 font-mono">Isolated database and workflow partitions with independent rate limits</p>
                </div>
                {hasRole('platform_admin') && (
                  <button
                    onClick={() => setShowTenantForm(!showTenantForm)}
                    className="px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center gap-1.5 transition"
                  >
                    <Plus className="h-3.5 w-3.5" /> Provision New Tenant
                  </button>
                )}
              </div>

              {/* Create Tenant Form */}
              {showTenantForm && (
                <form onSubmit={handleCreateTenant} className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl space-y-4 font-mono">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Organization Name</label>
                      <input
                        type="text"
                        value={newTenantName}
                        onChange={(e) => setNewTenantName(e.target.value)}
                        placeholder="Acme Enterprise Corp"
                        required
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Admin Full Name</label>
                      <input
                        type="text"
                        value={newTenantAdminName}
                        onChange={(e) => setNewTenantAdminName(e.target.value)}
                        placeholder="Jane Doe"
                        required
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Admin Email</label>
                      <input
                        type="email"
                        value={newTenantAdminEmail}
                        onChange={(e) => setNewTenantAdminEmail(e.target.value)}
                        placeholder="admin@acme.com"
                        required
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Admin Password</label>
                      <input
                        type="password"
                        value={newTenantAdminPassword}
                        onChange={(e) => setNewTenantAdminPassword(e.target.value)}
                        placeholder="Minimum 8 characters"
                        required
                        minLength={8}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100"
                      />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setShowTenantForm(false)}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 text-xs"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-3 py-1.5 rounded-lg bg-emerald-500 text-slate-950 font-bold text-xs"
                    >
                      Provision Tenant
                    </button>
                  </div>
                </form>
              )}

              {/* Tenants Grid */}
              {tenants.length === 0 && (
                <div className="py-6 text-center text-slate-500 font-mono text-xs">
                  {loadingTenants ? 'Loading tenant organizations...' : 'No tenant organizations found.'}
                </div>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
                {tenants.map((t) => (
                  <div
                    key={t.id}
                    className={`p-4 rounded-xl border transition ${
                      activeTenantId === t.id
                        ? 'bg-slate-900 border-emerald-500/40 shadow-lg shadow-emerald-500/5'
                        : 'bg-slate-900/60 border-slate-800'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Building className="h-4 w-4 text-emerald-400" />
                        <span className="font-bold text-slate-100 text-sm">{t.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {activeTenantId === t.id ? (
                          <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[10px] border border-emerald-500/30">
                            Active Context
                          </span>
                        ) : (
                          hasRole('platform_admin') && (
                            <button
                              onClick={() => switchTenant(t.id)}
                              className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] border border-slate-700 transition"
                            >
                              Switch
                            </button>
                          )
                        )}
                      </div>
                    </div>

                    <div className="space-y-2 text-slate-400">
                      <div className="flex justify-between">
                        <span>Tenant ID:</span>
                        <span className="text-slate-300 font-semibold">{t.id}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Rate Limit Quota:</span>
                        <span className="text-emerald-400">{t.quotas.rate_limit_rps} RPS (burst: {t.quotas.rate_limit_burst})</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Max Daily Executions:</span>
                        <span className="text-slate-300">{t.quotas.max_daily_executions.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Max Workflows:</span>
                        <span className="text-slate-300">{t.quotas.max_workflows}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sub-Tab 3: Tenant Users */}
          {activeSubTab === 'users' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-200 font-mono">Users in Tenant ({activeTenantId})</h3>
                  <p className="text-xs text-slate-400 font-mono">Authorized users and assigned role-based permissions</p>
                </div>
                {(hasRole('platform_admin') || hasRole('tenant_admin')) && (
                  <button
                    onClick={() => setShowUserForm(!showUserForm)}
                    className="px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center gap-1.5 transition"
                  >
                    <Plus className="h-3.5 w-3.5" /> Provision User
                  </button>
                )}
              </div>

              {/* Create User Form */}
              {showUserForm && (
                <form onSubmit={handleCreateUser} className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl space-y-4 font-mono">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Full Name</label>
                      <input
                        type="text"
                        value={newUserFullName}
                        onChange={(e) => setNewUserFullName(e.target.value)}
                        placeholder="Alice Smith"
                        required
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Email</label>
                      <input
                        type="email"
                        value={newUserEmail}
                        onChange={(e) => setNewUserEmail(e.target.value)}
                        placeholder="alice@domain.com"
                        required
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Password</label>
                      <input
                        type="password"
                        value={newUserPassword}
                        onChange={(e) => setNewUserPassword(e.target.value)}
                        placeholder="Minimum 8 characters"
                        required
                        minLength={8}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Role</label>
                      <select
                        value={newUserRole}
                        onChange={(e) => setNewUserRole(e.target.value as Role)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100"
                      >
                        <option value="viewer">viewer (Read-only)</option>
                        <option value="analyst">analyst (Predictions & RCA)</option>
                        <option value="operator">operator (Remediation & Actuation)</option>
                        <option value="tenant_admin">tenant_admin (Tenant Administration)</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setShowUserForm(false)}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 text-xs"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-3 py-1.5 rounded-lg bg-emerald-500 text-slate-950 font-bold text-xs"
                    >
                      Create User
                    </button>
                  </div>
                </form>
              )}

              {/* Users Table */}
              <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
                <table className="w-full text-left border-collapse font-mono text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-950/60 text-slate-400">
                      <th className="py-2.5 px-4 font-semibold">User Name</th>
                      <th className="py-2.5 px-4 font-semibold">Email</th>
                      <th className="py-2.5 px-4 font-semibold">Roles</th>
                      <th className="py-2.5 px-4 font-semibold">Created At</th>
                      <th className="py-2.5 px-4 font-semibold">Last Login</th>
                      <th className="py-2.5 px-4 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {tenantUsers.length === 0 && (
                      <tr>
                        <td colSpan={6} className="py-6 text-center text-slate-500">
                          {loadingUsers ? 'Loading users...' : 'No users provisioned in this tenant.'}
                        </td>

                      </tr>
                    )}
                    {tenantUsers.map((u) => (
                      <tr key={u.id} className="hover:bg-slate-800/30 transition">
                        <td className="py-2.5 px-4 font-semibold text-slate-200">{u.full_name}</td>
                        <td className="py-2.5 px-4 text-slate-300">{u.email}</td>
                        <td className="py-2.5 px-4">
                          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-cyan-300 border border-slate-700 text-[10px]">
                            {u.roles.join(', ')}
                          </span>
                        </td>
                        <td className="py-2.5 px-4 text-slate-400">{new Date(u.created_at).toLocaleDateString()}</td>
                        <td className="py-2.5 px-4 text-slate-400">{u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : 'Never'}</td>
                        <td className="py-2.5 px-4">
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            ACTIVE
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
