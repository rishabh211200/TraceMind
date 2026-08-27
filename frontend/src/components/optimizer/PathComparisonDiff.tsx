import React from 'react';
import { ExpectedSavings, PathMetrics } from '../../types/optimizer';
import { ArrowRight, CheckCircle, Clock, DollarSign, ShieldCheck, Zap } from 'lucide-react';

interface PathComparisonDiffProps {
  currentPath: PathMetrics | null;
  recommendedPath: PathMetrics;
  expectedSavings: ExpectedSavings;
}

export const PathComparisonDiff: React.FC<PathComparisonDiffProps> = ({
  currentPath,
  recommendedPath,
  expectedSavings,
}) => {
  const renderStepBadge = (step: { service: string; operation: string; is_database?: boolean; is_cache?: boolean; is_fallback?: boolean }) => {
    let bg = 'bg-slate-800 border-slate-700 text-slate-300';
    let label = step.service;

    if (step.is_cache || step.service.includes('cache')) {
      bg = 'bg-emerald-950/70 border-emerald-600/60 text-emerald-300 font-semibold shadow-sm';
      label = `⚡ ${step.service}`;
    } else if (step.is_database || step.service.includes('db')) {
      bg = 'bg-amber-950/60 border-amber-600/50 text-amber-300';
      label = `🗄️ ${step.service}`;
    } else if (step.is_fallback || step.service.includes('fallback') || step.service.includes('secondary')) {
      bg = 'bg-purple-950/60 border-purple-600/50 text-purple-300';
      label = `🛡️ ${step.service}`;
    }

    return (
      <span
        key={`${step.service}:${step.operation}`}
        className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs border ${bg} transition-all`}
        title={`Operation: ${step.operation}`}
      >
        {label}
      </span>
    );
  };

  return (
    <div className="bg-slate-900/90 backdrop-blur border border-slate-800/80 rounded-xl p-5 shadow-xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
            <Zap className="w-4 h-4 text-emerald-400" />
            Execution Path Routing Comparison & Projected Delta Savings
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Side-by-side comparison of baseline execution vs recommended optimal path.
          </p>
        </div>

        {/* Delta Savings Highlight Badges */}
        <div className="flex flex-wrap items-center gap-2">
          {expectedSavings.latency_reduction_pct !== 0 && (
            <span
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1 border ${
                expectedSavings.latency_reduction_pct > 0
                  ? 'bg-emerald-950/60 border-emerald-600 text-emerald-300'
                  : 'bg-rose-950/60 border-rose-600 text-rose-300'
              }`}
            >
              <Clock className="w-3.5 h-3.5" />
              {expectedSavings.latency_reduction_pct > 0 ? '-' : '+'}
              {Math.abs(expectedSavings.latency_reduction_pct)}% Latency (
              {Math.abs(expectedSavings.absolute_latency_delta_ms)}ms)
            </span>
          )}

          {expectedSavings.cost_reduction_pct !== 0 && (
            <span
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1 border ${
                expectedSavings.cost_reduction_pct > 0
                  ? 'bg-emerald-950/60 border-emerald-600 text-emerald-300'
                  : 'bg-amber-950/60 border-amber-600 text-amber-300'
              }`}
            >
              <DollarSign className="w-3.5 h-3.5" />
              {expectedSavings.cost_reduction_pct > 0 ? '-' : '+'}
              {Math.abs(expectedSavings.cost_reduction_pct)}% Modeled Cost (
              {Math.abs(expectedSavings.absolute_cost_delta_units)}u)
            </span>
          )}

          {expectedSavings.reliability_gain_pct !== 0 && (
            <span
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1 border ${
                expectedSavings.reliability_gain_pct >= 0
                  ? 'bg-emerald-950/60 border-emerald-600 text-emerald-300'
                  : 'bg-rose-950/60 border-rose-600 text-rose-300'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              {expectedSavings.reliability_gain_pct >= 0 ? '+' : ''}
              {expectedSavings.reliability_gain_pct}% Reliability
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Baseline / Current Path Card */}
        <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wide">
              Baseline / Current Path
            </span>
            <span className="px-2 py-0.5 bg-slate-800 text-slate-300 font-mono text-xs rounded">
              {currentPath ? currentPath.path_id : 'Default Baseline'}
            </span>
          </div>

          {currentPath ? (
            <>
              <div className="flex items-center gap-4 text-xs text-slate-300 bg-slate-900/60 p-2.5 rounded border border-slate-800/60">
                <span>
                  Latency: <strong>{currentPath.observed_latency_ms}ms</strong> (P95: {currentPath.observed_p95_latency_ms}ms)
                </span>
                <span>•</span>
                <span>
                  Cost: <strong>{currentPath.modeled_cost_units}u</strong>
                </span>
                <span>•</span>
                <span>
                  Reliability: <strong>{(currentPath.observed_reliability * 100).toFixed(1)}%</strong>
                </span>
              </div>

              <div>
                <span className="text-[11px] text-slate-400 block mb-1.5 font-medium">
                  Service Execution Sequence ({currentPath.steps.length} steps):
                </span>
                <div className="flex flex-wrap items-center gap-1.5">
                  {currentPath.steps.map((step, idx) => (
                    <React.Fragment key={`${step.service}-${idx}`}>
                      {renderStepBadge(step)}
                      {idx < currentPath.steps.length - 1 && (
                        <ArrowRight className="w-3 h-3 text-slate-600" />
                      )}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="text-xs text-slate-400 py-4 text-center">
              No specific baseline path selected.
            </div>
          )}
        </div>

        {/* Recommended Optimal Path Card */}
        <div className="bg-emerald-950/20 border border-emerald-800/50 rounded-lg p-4 space-y-3 shadow-inner">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-emerald-400 uppercase tracking-wide flex items-center gap-1.5">
              <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
              Recommended Optimal Path
            </span>
            <span className="px-2 py-0.5 bg-emerald-900/80 text-emerald-200 font-mono text-xs font-bold rounded border border-emerald-700/60">
              {recommendedPath.path_id} ★
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs text-emerald-200 bg-emerald-950/40 p-2.5 rounded border border-emerald-800/60">
            <span>
              Latency: <strong>{recommendedPath.observed_latency_ms}ms</strong> (P95: {recommendedPath.observed_p95_latency_ms}ms)
            </span>
            <span>•</span>
            <span>
              Cost: <strong>{recommendedPath.modeled_cost_units}u</strong>
            </span>
            <span>•</span>
            <span>
              Reliability: <strong>{(recommendedPath.observed_reliability * 100).toFixed(1)}%</strong>
            </span>
          </div>

          <div>
            <span className="text-[11px] text-emerald-300/80 block mb-1.5 font-medium">
              Optimized Execution Sequence ({recommendedPath.steps.length} steps):
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              {recommendedPath.steps.map((step, idx) => (
                <React.Fragment key={`rec-${step.service}-${idx}`}>
                  {renderStepBadge(step)}
                  {idx < recommendedPath.steps.length - 1 && (
                    <ArrowRight className="w-3 h-3 text-emerald-600/70" />
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
