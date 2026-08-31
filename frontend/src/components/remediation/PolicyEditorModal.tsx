import React from 'react';
import { ShieldCheck, X } from 'lucide-react';
import { RemediationPolicy } from '../../types/remediation';

interface PolicyEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  policies: RemediationPolicy[];
}

export const PolicyEditorModal: React.FC<PolicyEditorModalProps> = ({
  isOpen,
  onClose,
  policies,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-100">
                Declarative Self-Healing Policies
              </h3>
              <p className="text-xs text-slate-400">
                Deterministic governance rules & autonomous mode boundaries
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
        <div className="p-6 overflow-y-auto space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {policies.map((policy) => (
              <div
                key={policy.id}
                className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 flex flex-col justify-between space-y-3"
              >
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-mono text-cyan-400 font-medium">
                      {policy.id}
                    </span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                        policy.execution_mode === 'AUTONOMOUS'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          : policy.execution_mode === 'SUPERVISED'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                          : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                      }`}
                    >
                      {policy.execution_mode}
                    </span>
                  </div>
                  <h4 className="text-sm font-semibold text-slate-200">{policy.name}</h4>
                  <p className="text-xs text-slate-400 mt-1">
                    Target Fault: <span className="text-slate-300 font-mono">{policy.incident_category}</span>
                  </p>
                </div>

                <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-700/40 text-[11px]">
                  <div>
                    <span className="text-slate-500 block">Action</span>
                    <span className="font-mono text-slate-300">{policy.action_type}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Blast Radius</span>
                    <span className="font-mono text-slate-300">{(policy.max_blast_radius * 100).toFixed(0)}%</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Cooldown</span>
                    <span className="font-mono text-slate-300">{policy.cooldown_seconds}s</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
