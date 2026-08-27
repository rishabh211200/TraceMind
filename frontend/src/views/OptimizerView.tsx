import React, { useEffect, useState } from 'react';
import {
  getOptimizerStats,
  recommendOptimalPath,
} from '../api/optimizer';
import {
  OptimizationReport,
  OptimizerStats,
  PathMetrics,
} from '../types/optimizer';
import { ParetoFrontierChart } from '../components/optimizer/ParetoFrontierChart';
import { PathComparisonDiff } from '../components/optimizer/PathComparisonDiff';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Compass,
  DollarSign,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Zap,
} from 'lucide-react';

export const OptimizerView: React.FC = () => {
  const [loading, setLoading] = useState<boolean>(true);
  const [recommending, setRecommending] = useState<boolean>(false);
  const [report, setReport] = useState<OptimizationReport | null>(null);
  const [stats, setStats] = useState<OptimizerStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Strategy Weights
  const [weightLatency, setWeightLatency] = useState<number>(0.40);
  const [weightCost, setWeightCost] = useState<number>(0.30);
  const [weightReliability, setWeightReliability] = useState<number>(0.30);

  // Advisory Incident Diversion
  const [incidentCulprit, setIncidentCulprit] = useState<string>('');

  // Selected path for inspection
  const [inspectedPath, setInspectedPath] = useState<PathMetrics | null>(null);

  const fetchOptimization = async (
    wLat = weightLatency,
    wCost = weightCost,
    wRel = weightReliability,
    culprit = incidentCulprit
  ) => {
    setRecommending(true);
    setError(null);
    try {
      const rec = await recommendOptimalPath({
        workflow_definition_id: 'order_fulfillment',
        weight_latency: wLat,
        weight_cost: wCost,
        weight_reliability: wRel,
        active_incident_culprit: culprit || undefined,
        persist_to_db: false,
      });
      setReport(rec);
      setInspectedPath(rec.recommended_path);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to compute optimization recommendation.');
    } finally {
      setRecommending(false);
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const s = await getOptimizerStats();
      setStats(s);
    } catch {
      // Non-critical
    }
  };

  useEffect(() => {
    fetchOptimization();
    fetchStats();
  }, []);

  const handleApplyPreset = (lat: number, cost: number, rel: number) => {
    setWeightLatency(lat);
    setWeightCost(cost);
    setWeightReliability(rel);
    fetchOptimization(lat, cost, rel, incidentCulprit);
  };

  const handleSliderChange = (type: 'lat' | 'cost' | 'rel', val: number) => {
    let lat = weightLatency;
    let cost = weightCost;
    let rel = weightReliability;

    if (type === 'lat') lat = val;
    if (type === 'cost') cost = val;
    if (type === 'rel') rel = val;

    const total = lat + cost + rel || 1.0;
    const normLat = Number((lat / total).toFixed(2));
    const normCost = Number((cost / total).toFixed(2));
    const normRel = Number((1.0 - normLat - normCost).toFixed(2));

    setWeightLatency(normLat);
    setWeightCost(normCost);
    setWeightReliability(normRel);
    fetchOptimization(normLat, normCost, normRel, incidentCulprit);
  };

  const handleCulpritChange = (culprit: string) => {
    setIncidentCulprit(culprit);
    fetchOptimization(weightLatency, weightCost, weightReliability, culprit);
  };

  if (loading && !report) {
    return (
      <div className="flex items-center justify-center min-h-[500px]">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
          <span className="text-slate-400 text-sm font-medium">Computing Multi-Objective Pareto Frontier...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Header Title Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900/60 p-5 rounded-2xl border border-slate-800 shadow-xl">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-emerald-950/80 border border-emerald-700/60 rounded-xl text-emerald-400 shadow-inner">
              <Compass className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                Workflow Optimizer & Path Routing
                <span className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800">
                  Milestone 9
                </span>
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Deterministic 3D Pareto frontier optimization & advisory incident detour recommendations.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => fetchOptimization()}
            disabled={recommending}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${recommending ? 'animate-spin' : ''}`} />
            Recalculate
          </button>
        </div>
      </div>

      {/* Metric KPI Summary Cards */}
      {report && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl p-4">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
              Evaluated Paths
            </span>
            <div className="text-2xl font-bold font-mono text-slate-100 mt-1">
              {report.all_evaluated_paths.length}
            </div>
            <span className="text-[10px] text-slate-400 mt-0.5 block">
              {report.pareto_frontier.filter((p) => p.is_pareto_optimal).length} on Pareto frontier
            </span>
          </div>

          <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl p-4">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
              Recommended Path
            </span>
            <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
              {report.recommended_path.path_id} ★
            </div>
            <span className="text-[10px] text-slate-400 mt-0.5 block">
              {report.recommended_path.observed_latency_ms}ms · {report.recommended_path.modeled_cost_units}u
            </span>
          </div>

          <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl p-4">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
              Projected Latency Delta
            </span>
            <div className="text-2xl font-bold font-mono text-sky-400 mt-1">
              {report.expected_savings.latency_reduction_pct > 0 ? '-' : '+'}
              {Math.abs(report.expected_savings.latency_reduction_pct)}%
            </div>
            <span className="text-[10px] text-slate-400 mt-0.5 block">
              {Math.abs(report.expected_savings.absolute_latency_delta_ms)}ms savings
            </span>
          </div>

          <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl p-4">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
              Reliability / Stats
            </span>
            <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
              {(report.recommended_path.observed_reliability * 100).toFixed(1)}%
            </div>
            <span className="text-[10px] text-slate-400 mt-0.5 block">
              {stats?.total_optimizations || 1} optimization runs logged
            </span>
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 bg-rose-950/60 border border-rose-800/80 rounded-xl text-rose-200 text-xs flex items-center gap-2.5">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Advisory Incident Rationale Callout Banner */}
      {report && (
        <div
          className={`p-4 rounded-xl border flex items-start gap-3 shadow-lg ${
            report.active_incident_culprit
              ? 'bg-amber-950/40 border-amber-600/70 text-amber-100'
              : 'bg-emerald-950/40 border-emerald-600/60 text-emerald-100'
          }`}
        >
          <div className="p-1.5 rounded-lg bg-slate-900/60 mt-0.5">
            {report.active_incident_culprit ? (
              <AlertTriangle className="w-4 h-4 text-amber-400" />
            ) : (
              <Sparkles className="w-4 h-4 text-emerald-400" />
            )}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider">
                {report.active_incident_culprit
                  ? 'Active Bottleneck Advisory Detour'
                  : 'Multi-Objective Routing Recommendation'}
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900/80 font-bold">
                {report.recommended_path.path_id}
              </span>
            </div>
            <p className="text-xs text-slate-300 mt-1 leading-relaxed">
              {report.rationale}
            </p>
          </div>
        </div>
      )}

      {/* Controls: Presets, Objective Sliders & Incident Simulator */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Preset Strategy Buttons */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4.5 space-y-3">
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-emerald-400" />
            Optimization Presets
          </span>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <button
              onClick={() => handleApplyPreset(0.40, 0.30, 0.30)}
              className={`p-2.5 rounded-lg border text-left transition ${
                weightLatency === 0.40 && weightCost === 0.30
                  ? 'bg-emerald-950 border-emerald-500 text-emerald-200'
                  : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
              }`}
            >
              <div className="font-semibold">Balanced</div>
              <div className="text-[10px] text-slate-400">40% Lat, 30% Cost, 30% Rel</div>
            </button>

            <button
              onClick={() => handleApplyPreset(0.70, 0.15, 0.15)}
              className={`p-2.5 rounded-lg border text-left transition ${
                weightLatency === 0.70
                  ? 'bg-emerald-950 border-emerald-500 text-emerald-200'
                  : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
              }`}
            >
              <div className="font-semibold">Latency Priority</div>
              <div className="text-[10px] text-slate-400">70% Lat, 15% Cost, 15% Rel</div>
            </button>

            <button
              onClick={() => handleApplyPreset(0.20, 0.60, 0.20)}
              className={`p-2.5 rounded-lg border text-left transition ${
                weightCost === 0.60
                  ? 'bg-emerald-950 border-emerald-500 text-emerald-200'
                  : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
              }`}
            >
              <div className="font-semibold">Cost Minimizer</div>
              <div className="text-[10px] text-slate-400">20% Lat, 60% Cost, 20% Rel</div>
            </button>

            <button
              onClick={() => handleApplyPreset(0.20, 0.20, 0.60)}
              className={`p-2.5 rounded-lg border text-left transition ${
                weightReliability === 0.60
                  ? 'bg-emerald-950 border-emerald-500 text-emerald-200'
                  : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
              }`}
            >
              <div className="font-semibold">High Reliability</div>
              <div className="text-[10px] text-slate-400">20% Lat, 20% Cost, 60% Rel</div>
            </button>
          </div>
        </div>

        {/* Custom Normalized Sliders */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4.5 space-y-3">
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center justify-between">
            <span>Multi-Objective Weights</span>
            <span className="text-[10px] text-slate-400 font-normal">Auto-Normalized</span>
          </span>

          <div className="space-y-2.5 text-xs">
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-slate-400 flex items-center gap-1">
                  <Clock className="w-3 h-3 text-sky-400" /> Latency Weight:
                </span>
                <span className="font-mono font-bold text-sky-300">{Math.round(weightLatency * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={weightLatency}
                onChange={(e) => handleSliderChange('lat', parseFloat(e.target.value))}
                className="w-full accent-sky-500 h-1.5 bg-slate-800 rounded-lg"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span className="text-slate-400 flex items-center gap-1">
                  <DollarSign className="w-3 h-3 text-amber-400" /> Cost Weight:
                </span>
                <span className="font-mono font-bold text-amber-300">{Math.round(weightCost * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={weightCost}
                onChange={(e) => handleSliderChange('cost', parseFloat(e.target.value))}
                className="w-full accent-amber-500 h-1.5 bg-slate-800 rounded-lg"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span className="text-slate-400 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3 text-emerald-400" /> Reliability Weight:
                </span>
                <span className="font-mono font-bold text-emerald-300">{Math.round(weightReliability * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={weightReliability}
                onChange={(e) => handleSliderChange('rel', parseFloat(e.target.value))}
                className="w-full accent-emerald-500 h-1.5 bg-slate-800 rounded-lg"
              />
            </div>
          </div>
        </div>

        {/* Advisory Incident Simulation Detour */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4.5 space-y-3 flex flex-col justify-between">
          <div>
            <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
              Advisory Incident Detour
            </span>
            <p className="text-xs text-slate-400 mt-1">
              Simulate an active bottleneck on a culprit microservice to trigger automated diversion routing.
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-[11px] text-slate-400 font-medium block">
              Active Culprit Component:
            </label>
            <select
              value={incidentCulprit}
              onChange={(e) => handleCulpritChange(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="">None (Nominal Operations)</option>
              <option value="inventory-db">inventory-db (Database Saturation)</option>
              <option value="customer-db">customer-db (Slow Queries)</option>
              <option value="payment-gateway">payment-gateway (Transit Latency Spike)</option>
              <option value="pricing-service">pricing-service (Service Outage)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Visual Analytics Grid: Pareto Frontier & Path Comparison Diff */}
      {report && (
        <div className="grid grid-cols-1 gap-6">
          <ParetoFrontierChart
            points={report.pareto_frontier}
            selectedPathId={inspectedPath?.path_id}
            recommendedPathId={report.recommended_path.path_id}
            onSelectPath={(pid) => {
              const found = report.all_evaluated_paths.find((p) => p.path_id === pid);
              if (found) setInspectedPath(found);
            }}
          />

          <PathComparisonDiff
            currentPath={report.current_path}
            recommendedPath={report.recommended_path}
            expectedSavings={report.expected_savings}
          />
        </div>
      )}

      {/* Candidate Paths Evaluation Table */}
      {report && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
          <div className="p-4 bg-slate-950/60 border-b border-slate-800 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              Candidate Execution Paths Evaluation & Pareto Status
            </h3>
            <span className="text-xs text-slate-400">
              {report.all_evaluated_paths.length} candidate paths evaluated
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800 uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="px-4 py-3">Path ID</th>
                  <th className="px-4 py-3">Execution Sequence</th>
                  <th className="px-4 py-3 text-right">Observed Latency</th>
                  <th className="px-4 py-3 text-right">Modeled Cost</th>
                  <th className="px-4 py-3 text-right">Reliability</th>
                  <th className="px-4 py-3 text-right">Sample N</th>
                  <th className="px-4 py-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {report.all_evaluated_paths.map((p) => {
                  const pt = report.pareto_frontier.find((point) => point.path_id === p.path_id);
                  const isRec = p.path_id === report.recommended_path.path_id;
                  const isSelected = p.path_id === inspectedPath?.path_id;

                  return (
                    <tr
                      key={p.path_id}
                      onClick={() => setInspectedPath(p)}
                      className={`cursor-pointer transition-colors ${
                        isRec
                          ? 'bg-emerald-950/30 hover:bg-emerald-950/50'
                          : isSelected
                          ? 'bg-sky-950/30 hover:bg-sky-950/50'
                          : 'hover:bg-slate-800/40'
                      }`}
                    >
                      <td className="px-4 py-3 font-mono font-bold text-slate-200">
                        {p.path_id}
                        {isRec && <span className="text-emerald-400 ml-1">★</span>}
                      </td>
                      <td className="px-4 py-3 text-slate-300 max-w-xs truncate" title={p.step_signatures.join(' → ')}>
                        {p.step_signatures.join(' → ')}
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-medium text-sky-300">
                        {p.observed_latency_ms} ms
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-medium text-amber-300">
                        {p.modeled_cost_units} u
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-medium text-emerald-300">
                        {(p.observed_reliability * 100).toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-slate-400">
                        {p.observation_count}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {isRec ? (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-950 border border-emerald-700 text-emerald-300">
                            Recommended
                          </span>
                        ) : pt?.is_pareto_optimal ? (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-950/60 border border-emerald-800 text-emerald-400">
                            Pareto Optimal
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-800 text-slate-400">
                            Dominated
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
