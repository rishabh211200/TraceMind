import React from 'react';
import {
  Activity,
  CheckCircle,
  Play,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  X,
} from 'lucide-react';
import { RemediationPlan } from '../../types/remediation';

interface PlanDetailsModalProps {
  plan: RemediationPlan | null;
  isOpen: boolean;
  onClose: () => void;
  onExecute: (planId: string) => void;
  onRollback: (planId: string) => void;
  isExecuting: boolean;
}

export const PlanDetailsModal: React.FC<PlanDetailsModalProps> = ({
  plan,
  isOpen,
  onClose,
  onExecute,
  onRollback,
  isExecuting,
}) => {
  if (!isOpen || !plan) return null;

  const canExecute = plan.status === 'STAGED' && plan.execution_mode !== 'ADVISORY';
  const canRollback = plan.status === 'ACTIVE_VERIFYING' || plan.status === 'SUCCEEDED';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-cyan-500/10 rounded-lg text-cyan-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-lg font-semibold text-slate-100">{plan.id}</h3>
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
              </div>
              <p className="text-xs text-slate-400 font-mono">
                Workflow: {plan.workflow_definition_id} | Target: {plan.target_service}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Action Overview Cards */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-3">
              <span className="text-xs text-slate-400 block mb-1">Action Type</span>
              <span className="text-sm font-semibold text-cyan-300 font-mono">
                {plan.action_type}
              </span>
            </div>
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-3">
              <span className="text-xs text-slate-400 block mb-1">Execution Mode</span>
              <span className="text-sm font-semibold text-slate-200 font-mono">
                {plan.execution_mode}
              </span>
            </div>
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-3">
              <span className="text-xs text-slate-400 block mb-1">Blast Radius</span>
              <span className="text-sm font-semibold text-amber-300 font-mono">
                {(plan.blast_radius_pct * 100).toFixed(1)}%
              </span>
            </div>
          </div>

          {/* Safety Invariant Report */}
          {plan.safety_report && (
            <div className="bg-slate-800/30 border border-slate-700/40 rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-sm font-semibold text-slate-200">
                  {plan.safety_report.is_safe ? (
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <ShieldAlert className="w-4 h-4 text-amber-400" />
                  )}
                  <span>Deterministic Safety Invariant Evaluation</span>
                </div>
                <span
                  className={`text-xs px-2 py-0.5 rounded font-bold ${
                    plan.safety_report.is_safe
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : 'bg-amber-500/20 text-amber-300'
                  }`}
                >
                  {plan.safety_report.is_safe ? 'ALL INVARIANTS PASSED' : 'INVARIANT REJECTION'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs pt-2">
                <div className="flex items-center space-x-1.5 text-slate-300">
                  <CheckCircle className={`w-3.5 h-3.5 ${plan.safety_report.blast_radius_passed ? 'text-emerald-400' : 'text-red-400'}`} />
                  <span>Blast Radius Limit Check</span>
                </div>
                <div className="flex items-center space-x-1.5 text-slate-300">
                  <CheckCircle className={`w-3.5 h-3.5 ${plan.safety_report.anti_flapping_passed ? 'text-emerald-400' : 'text-red-400'}`} />
                  <span>Anti-Flapping / Cooldown Check</span>
                </div>
                <div className="flex items-center space-x-1.5 text-slate-300">
                  <CheckCircle className={`w-3.5 h-3.5 ${plan.safety_report.acyclicity_passed ? 'text-emerald-400' : 'text-red-400'}`} />
                  <span>Causal Dependency Acyclicity Check</span>
                </div>
                <div className="flex items-center space-x-1.5 text-slate-300">
                  <CheckCircle className={`w-3.5 h-3.5 ${plan.safety_report.capacity_headroom_passed ? 'text-emerald-400' : 'text-red-400'}`} />
                  <span>Target Path Capacity Headroom Check</span>
                </div>
              </div>
            </div>
          )}

          {/* Action Parameters & Exact State Snapshot */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              Target Routing Parameters & Idempotency Key
            </h4>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs font-mono text-slate-300 overflow-x-auto space-y-1">
              <div className="text-slate-500">// SHA-256 Idempotency Key:</div>
              <div className="text-cyan-400">{plan.idempotency_key}</div>
              <div className="text-slate-500 pt-2">// Target Parameters:</div>
              <div>{JSON.stringify(plan.target_parameters, null, 2)}</div>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded-lg transition-colors"
          >
            Close
          </button>
          <div className="flex items-center space-x-3">
            {canRollback && (
              <button
                onClick={() => onRollback(plan.id)}
                disabled={isExecuting}
                className="flex items-center space-x-2 px-4 py-2 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/40 text-sm font-semibold rounded-lg transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Emergency Rollback</span>
              </button>
            )}
            {canExecute && (
              <button
                onClick={() => onExecute(plan.id)}
                disabled={isExecuting}
                className="flex items-center space-x-2 px-5 py-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-sm font-semibold rounded-lg shadow-lg shadow-cyan-500/20 transition-all"
              >
                <Play className="w-4 h-4" />
                <span>{isExecuting ? 'Actuating...' : 'Authorize & Actuate'}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
