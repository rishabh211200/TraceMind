import React from 'react';
import { Play, RotateCcw, ShieldAlert, ShieldCheck } from 'lucide-react';

interface RemediationActionCardProps {
  planId: string;
  actionType: string;
  targetService: string;
  blastRadius: number;
  isSafe: boolean;
  status: string;
  onActuate?: (planId: string) => void;
  onRollback?: (planId: string) => void;
  isProcessing?: boolean;
}

export const RemediationActionCard: React.FC<RemediationActionCardProps> = ({
  planId,
  actionType,
  targetService,
  blastRadius,
  isSafe,
  status,
  onActuate,
  onRollback,
  isProcessing = false,
}) => {
  return (
    <div className="my-3 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border border-cyan-500/30 rounded-xl p-4 shadow-lg shadow-cyan-950/30 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          {isSafe ? (
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
          ) : (
            <ShieldAlert className="w-5 h-5 text-amber-400" />
          )}
          <span className="text-sm font-semibold text-slate-100">
            Self-Healing Action Plan
          </span>
        </div>
        <span
          className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
            status === 'SUCCEEDED'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
              : status === 'ROLLED_BACK'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
              : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
          }`}
        >
          {status}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800 text-xs">
        <div>
          <span className="text-slate-400 block text-[10px]">Action</span>
          <span className="font-mono text-cyan-300 font-medium">{actionType}</span>
        </div>
        <div>
          <span className="text-slate-400 block text-[10px]">Target</span>
          <span className="font-mono text-slate-200 font-medium">{targetService}</span>
        </div>
        <div>
          <span className="text-slate-400 block text-[10px]">Blast Radius</span>
          <span className="font-mono text-amber-300 font-medium">{(blastRadius * 100).toFixed(0)}%</span>
        </div>
      </div>

      <div className="flex items-center justify-between pt-1">
        <span className="text-xs font-mono text-slate-400">ID: {planId}</span>
        <div className="flex items-center space-x-2">
          {status === 'SUCCEEDED' && onRollback && (
            <button
              onClick={() => onRollback(planId)}
              disabled={isProcessing}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/40 text-xs font-semibold rounded-lg transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Rollback</span>
            </button>
          )}
          {status === 'STAGED' && onActuate && (
            <button
              onClick={() => onActuate(planId)}
              disabled={isProcessing}
              className="flex items-center space-x-1.5 px-3.5 py-1.5 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-xs font-semibold rounded-lg shadow transition-all"
            >
              <Play className="w-3.5 h-3.5" />
              <span>{isProcessing ? 'Actuating...' : 'Authorize & Actuate'}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
