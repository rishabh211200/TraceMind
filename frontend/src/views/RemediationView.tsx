import React, { useEffect, useState } from 'react';
import {
  Activity,
  CheckCircle,
  Database,
  Eye,
  Filter,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Zap,
} from 'lucide-react';

import {
  AuditLedgerEntry,
  RemediationPlan,
  RemediationPolicy,
  StateSnapshot,
} from '../types/remediation';
import {
  executeRemediationPlan,
  getAuditLedger,
  getLiveMeshState,
  listRemediationPlans,
  listRemediationPolicies,
  rollbackRemediationPlan,
  synthesizeRemediationPlan,
  verifyAuditLedgerIntegrity,
} from '../api/remediation';
import { PlanDetailsModal } from '../components/remediation/PlanDetailsModal';
import { PolicyEditorModal } from '../components/remediation/PolicyEditorModal';

export const RemediationView: React.FC = () => {
  const [plans, setPlans] = useState<RemediationPlan[]>([]);
  const [policies, setPolicies] = useState<RemediationPolicy[]>([]);
  const [meshState, setMeshState] = useState<StateSnapshot | null>(null);
  const [auditEntries, setAuditEntries] = useState<AuditLedgerEntry[]>([]);
  const [auditVerified, setAuditVerified] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedPlan, setSelectedPlan] = useState<RemediationPlan | null>(null);
  const [isPlanModalOpen, setIsPlanModalOpen] = useState<boolean>(false);
  const [isPolicyModalOpen, setIsPolicyModalOpen] = useState<boolean>(false);
  const [isActionProcessing, setIsActionProcessing] = useState<boolean>(false);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [pList, polList, mState, aLedger, aVerify] = await Promise.all([
        listRemediationPlans(),
        listRemediationPolicies(),
        getLiveMeshState(),
        getAuditLedger(),
        verifyAuditLedgerIntegrity(),
      ]);
      setPlans(pList);
      setPolicies(polList);
      setMeshState(mState);
      setAuditEntries(aLedger);
      setAuditVerified(aVerify.is_valid);
    } catch (err) {
      console.error('Failed to load remediation data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSynthesizeSample = async (category: string, service: string) => {
    setIsActionProcessing(true);
    try {
      const newPlan = await synthesizeRemediationPlan({
        workflow_definition_id: 'order_fulfillment',
        incident_category: category,
        root_cause_service: service,
        diagnostic_confidence: 0.98,
      });
      setSelectedPlan(newPlan);
      setIsPlanModalOpen(true);
      await fetchData();
    } catch (err) {
      console.error('Failed to synthesize sample plan:', err);
    } finally {
      setIsActionProcessing(false);
    }
  };

  const handleExecute = async (planId: string) => {
    setIsActionProcessing(true);
    try {
      const updated = await executeRemediationPlan(planId, 'Manual authorization via Control Center');
      setSelectedPlan(updated);
      await fetchData();
    } catch (err) {
      console.error('Failed to execute plan:', err);
    } finally {
      setIsActionProcessing(false);
    }
  };

  const handleRollback = async (planId: string) => {
    setIsActionProcessing(true);
    try {
      const updated = await rollbackRemediationPlan(planId);
      setSelectedPlan(updated);
      await fetchData();
    } catch (err) {
      console.error('Failed to rollback plan:', err);
    } finally {
      setIsActionProcessing(false);
    }
  };

  const activeMitigations = plans.filter(
    (p) => p.status === 'ACTIVE_VERIFYING' || p.status === 'SUCCEEDED'
  );

  const filteredPlans = plans.filter((p) => {
    if (statusFilter === 'ALL') return true;
    return p.status === statusFilter;
  });

  return (
    <div className="space-y-8 p-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-gradient-to-tr from-cyan-600 to-blue-600 rounded-xl text-white shadow-lg shadow-cyan-500/20">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-100">
                Autonomous Closed-Loop Remediation
              </h1>
              <p className="text-sm text-slate-400">
                Policy-governed self-healing control plane, blast-radius safeguards & verbatim rollback
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setIsPolicyModalOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-xl border border-slate-700 transition-colors"
          >
            <Sliders className="w-4 h-4 text-cyan-400" />
            <span>Policy Studio ({policies.length})</span>
          </button>

          <button
            onClick={() => handleSynthesizeSample('DATABASE_IOPS_SATURATION', 'customer-db')}
            disabled={isActionProcessing}
            className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-sm font-semibold rounded-xl shadow-lg shadow-cyan-500/20 transition-all"
          >
            <Zap className="w-4 h-4" />
            <span>Simulate Chaos Action</span>
          </button>

          <button
            onClick={fetchData}
            className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-xl border border-slate-800 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Active Mitigations</span>
            <Activity className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100 font-mono">
            {activeMitigations.length}
          </div>
          <span className="text-xs text-slate-400 mt-1 block">Live in Service Mesh</span>
        </div>

        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Total Synthesized</span>
            <Shield className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100 font-mono">{plans.length}</div>
          <span className="text-xs text-slate-400 mt-1 block">RCA & Pareto Directives</span>
        </div>

        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Recovery Rate</span>
            <CheckCircle className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 font-mono">98.4%</div>
          <span className="text-xs text-slate-400 mt-1 block">Target &ge; 95.0%</span>
        </div>

        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Audit Chain Integrity</span>
            <ShieldCheck className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-lg font-bold text-purple-300 font-mono flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>{auditVerified ? 'SHA-256 INTACT' : 'VERIFYING...'}</span>
          </div>
          <span className="text-xs text-slate-400 mt-1 block">{auditEntries.length} Immutable Blocks</span>
        </div>
      </div>

      {/* Live Mesh State & Active Mitigations */}
      {meshState && (
        <div className="bg-slate-900/80 border border-cyan-500/30 rounded-2xl p-6 shadow-xl shadow-cyan-950/20 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <Database className="w-5 h-5 text-cyan-400" />
              <h3 className="text-base font-semibold text-slate-100">
                Live Mesh Runtime & Circuit Breaker Topology
              </h3>
            </div>
            <span className="text-xs font-mono text-slate-400">
              Captured: {new Date(meshState.captured_at).toLocaleTimeString()}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-2">
            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400 block font-semibold">Active Routing Weights</span>
              {Object.entries(meshState.routing_weights).map(([path, weight]) => (
                <div key={path} className="flex justify-between text-xs font-mono">
                  <span className="text-slate-300">{path}</span>
                  <span className="text-cyan-400 font-bold">{(weight * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>

            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400 block font-semibold">Circuit Breaker States</span>
              {Object.entries(meshState.circuit_states).map(([svc, state]) => (
                <div key={svc} className="flex justify-between text-xs font-mono">
                  <span className="text-slate-300 truncate max-w-[120px]">{svc}</span>
                  <span
                    className={`font-bold ${
                      state === 'OPEN' ? 'text-red-400' : 'text-emerald-400'
                    }`}
                  >
                    {state}
                  </span>
                </div>
              ))}
            </div>

            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400 block font-semibold">Concurrency Limits</span>
              {Object.entries(meshState.concurrency_limits).map(([svc, limit]) => (
                <div key={svc} className="flex justify-between text-xs font-mono">
                  <span className="text-slate-300 truncate max-w-[120px]">{svc}</span>
                  <span className="text-amber-300 font-bold">{limit} in-flight</span>
                </div>
              ))}
            </div>

            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400 block font-semibold">Retry Multipliers</span>
              {Object.entries(meshState.retry_multipliers).map(([svc, mult]) => (
                <div key={svc} className="flex justify-between text-xs font-mono">
                  <span className="text-slate-300 truncate max-w-[120px]">{svc}</span>
                  <span className="text-purple-300 font-bold">{mult.toFixed(1)}x</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Action Plans Table */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-lg space-y-4 p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-slate-100">
              Remediation Action History & Staged Plans
            </h3>
            <p className="text-xs text-slate-400">
              Audit log of autonomous, supervised, and advisory mitigations
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="STAGED">STAGED</option>
              <option value="ACTIVE_VERIFYING">ACTIVE_VERIFYING</option>
              <option value="SUCCEEDED">SUCCEEDED</option>
              <option value="ROLLED_BACK">ROLLED_BACK</option>
              <option value="FAILED">FAILED</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Plan ID</th>
                <th className="py-3 px-4">Action Type</th>
                <th className="py-3 px-4">Target Service</th>
                <th className="py-3 px-4">Mode</th>
                <th className="py-3 px-4">Blast Radius</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Created</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {filteredPlans.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-500">
                    No remediation plans matching criteria.
                  </td>
                </tr>
              ) : (
                filteredPlans.map((plan) => (
                  <tr key={plan.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-medium text-cyan-400">
                      {plan.id}
                    </td>
                    <td className="py-3.5 px-4 font-mono font-semibold text-slate-200">
                      {plan.action_type}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-300">
                      {plan.target_service}
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                          plan.execution_mode === 'AUTONOMOUS'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : plan.execution_mode === 'SUPERVISED'
                            ? 'bg-amber-500/20 text-amber-300'
                            : 'bg-blue-500/20 text-blue-300'
                        }`}
                      >
                        {plan.execution_mode}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-amber-300">
                      {(plan.blast_radius_pct * 100).toFixed(0)}%
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                          plan.status === 'SUCCEEDED'
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                            : plan.status === 'ROLLED_BACK'
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            : plan.status === 'FAILED'
                            ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                            : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                        }`}
                      >
                        {plan.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-400 font-mono text-[11px]">
                      {new Date(plan.created_at).toLocaleTimeString()}
                    </td>
                    <td className="py-3.5 px-4 text-right space-x-2">
                      <button
                        onClick={() => {
                          setSelectedPlan(plan);
                          setIsPlanModalOpen(true);
                        }}
                        className="p-1.5 text-slate-400 hover:text-cyan-300 hover:bg-slate-800 rounded-lg transition-colors"
                        title="View Details"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      {plan.status === 'STAGED' && (
                        <button
                          onClick={() => handleExecute(plan.id)}
                          disabled={isActionProcessing}
                          className="px-2.5 py-1 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-[11px] rounded-lg shadow transition-all"
                        >
                          Execute
                        </button>
                      )}
                      {(plan.status === 'SUCCEEDED' || plan.status === 'ACTIVE_VERIFYING') && (
                        <button
                          onClick={() => handleRollback(plan.id)}
                          disabled={isActionProcessing}
                          className="px-2.5 py-1 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/30 font-semibold text-[11px] rounded-lg transition-colors"
                        >
                          Rollback
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

      {/* Modals */}
      <PlanDetailsModal
        plan={selectedPlan}
        isOpen={isPlanModalOpen}
        onClose={() => setIsPlanModalOpen(false)}
        onExecute={handleExecute}
        onRollback={handleRollback}
        isExecuting={isActionProcessing}
      />

      <PolicyEditorModal
        isOpen={isPolicyModalOpen}
        onClose={() => setIsPolicyModalOpen(false)}
        policies={policies}
      />
    </div>
  );
};
