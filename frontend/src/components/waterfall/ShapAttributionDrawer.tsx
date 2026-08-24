import React from 'react';
import { Prediction } from '../../types/prediction';
import { Badge } from '../common/Badge';
import {
  BrainCircuit,
  X,
  TrendingUp,
  AlertTriangle,
  Clock,
  ShieldCheck,
  Zap,
} from 'lucide-react';

interface ShapAttributionDrawerProps {
  prediction: Prediction | null;
  onClose: () => void;
}

export const ShapAttributionDrawer: React.FC<ShapAttributionDrawerProps> = ({
  prediction,
  onClose,
}) => {
  if (!prediction) return null;

  const getRiskVariant = (risk: string) => {
    switch (risk) {
      case 'CRITICAL':
        return 'danger';
      case 'HIGH':
        return 'danger';
      case 'MEDIUM':
        return 'warning';
      default:
        return 'success';
    }
  };

  const getRiskIcon = (risk: string) => {
    switch (risk) {
      case 'CRITICAL':
      case 'HIGH':
        return <AlertTriangle className="h-5 w-5 text-rose-400" />;
      case 'MEDIUM':
        return <TrendingUp className="h-5 w-5 text-amber-400" />;
      default:
        return <ShieldCheck className="h-5 w-5 text-emerald-400" />;
    }
  };

  const contributions = prediction.top_contributions || [];
  const maxAbsAttr = Math.max(
    ...contributions.map((c) => Math.abs(c.contribution)),
    0.01
  );

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-lg bg-slate-900/95 border-l border-slate-800 shadow-2xl backdrop-blur-xl z-50 flex flex-col font-mono text-xs overflow-hidden animate-in slide-in-from-right duration-200">
      {/* Drawer Header */}
      <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-lg bg-purple-500/10 border border-purple-500/30 text-purple-400">
            <BrainCircuit className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-bold text-slate-100 text-sm">
              ML Failure Prediction & TreeSHAP
            </h3>
            <span className="text-[10px] text-slate-500">
              Execution: {prediction.execution_id} &bull; Step {prediction.step_index}
            </span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Drawer Body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {/* Risk & Latency KPI Cards */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-500 font-semibold">FAILURE RISK</span>
              {getRiskIcon(prediction.predicted_risk_level)}
            </div>
            <div className="text-xl font-bold text-slate-100">
              {(prediction.failure_probability * 100).toFixed(1)}%
            </div>
            <div className="pt-0.5">
              <Badge variant={getRiskVariant(prediction.predicted_risk_level)}>
                {prediction.predicted_risk_level} RISK
              </Badge>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-500 font-semibold">FORECAST LATENCY</span>
              <Clock className="h-5 w-5 text-sky-400" />
            </div>
            <div className="text-xl font-bold text-sky-400">
              {prediction.predicted_latency_ms.toFixed(1)} <span className="text-xs text-slate-400">ms</span>
            </div>
            <span className="text-[10px] text-slate-500 block">
              Confidence: {(prediction.confidence * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        {/* TreeSHAP Feature Attributions Section */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1.5 text-slate-200 font-semibold">
              <Zap className="h-4 w-4 text-amber-400" />
              <span>TreeSHAP Feature Attributions</span>
            </div>
            <span className="text-[10px] text-slate-500">
              Additive: &sum; &phi;<sub>i</sub> = f(x)
            </span>
          </div>

          <p className="text-[11px] text-slate-400 leading-relaxed">
            Exact Shapley attributions computed from tree paths. Red bars elevate failure risk; green bars indicate healthy baseline execution.
          </p>

          <div className="space-y-3 pt-1">
            {contributions.map((c) => {
              const isPositive = c.contribution > 0;
              const barWidthPercent = Math.min(100, Math.round((Math.abs(c.contribution) / maxAbsAttr) * 100));

              return (
                <div
                  key={c.feature_name}
                  className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 space-y-2 hover:border-slate-700 transition"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-200 text-[11px]">
                      {c.feature_name.replace(/_/g, ' ')}
                    </span>
                    <span
                      className={`font-bold ${
                        isPositive ? 'text-rose-400' : 'text-emerald-400'
                      }`}
                    >
                      {isPositive ? '+' : ''}
                      {c.contribution.toFixed(3)}
                    </span>
                  </div>

                  {/* Horizontal Attribution Bar */}
                  <div className="h-1.5 w-full bg-slate-900 rounded-full overflow-hidden flex">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        isPositive ? 'bg-rose-500' : 'bg-emerald-500'
                      }`}
                      style={{ width: `${barWidthPercent}%` }}
                    />
                  </div>

                  {/* Diagnostic Explanation */}
                  {c.description && (
                    <p className="text-[10px] text-slate-400 leading-tight pt-0.5">
                      &bull; {c.description}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Feature Vector Table */}
        <div className="space-y-2 pt-2">
          <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider block">
            Extracted Feature Vector Values
          </span>
          <div className="rounded-lg bg-slate-950/80 border border-slate-800/80 p-3 max-h-48 overflow-y-auto divide-y divide-slate-900 text-[10px]">
            {Object.entries(prediction.feature_vector || {}).map(([key, val]) => (
              <div key={key} className="py-1 flex items-center justify-between">
                <span className="text-slate-400">{key}</span>
                <span className="text-slate-200 font-bold">
                  {typeof val === 'number' ? val.toFixed(2) : String(val)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Drawer Footer */}
      <div className="p-4 border-t border-slate-800 bg-slate-950 text-[10px] text-slate-500 flex items-center justify-between">
        <span>Model: {prediction.model_name} (v{prediction.model_version})</span>
        <span>{new Date(prediction.created_at).toLocaleTimeString()}</span>
      </div>
    </div>
  );
};
