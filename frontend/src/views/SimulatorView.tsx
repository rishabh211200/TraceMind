import React, { useEffect, useState, useCallback } from 'react';
import { simulatorApi } from '../api/simulator';
import {
  ChaosInjectionResponse,
  ChaosScenarioInfo,
  SimulationGenerateResponse,
} from '../types/simulator';
import { Badge } from '../components/common/Badge';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { SkeletonCard } from '../components/common/LoadingSkeleton';
import {
  Flame,
  Zap,
  Play,
  CheckCircle2,
  ArrowRight,
  ShieldAlert,
  Layers,
} from 'lucide-react';

interface SimulatorViewProps {
  onNavigateExecutions?: () => void;
}

export const SimulatorView: React.FC<SimulatorViewProps> = ({ onNavigateExecutions }) => {
  const [scenarios, setScenarios] = useState<ChaosScenarioInfo[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Simulation Form State
  const [simWorkflows, setSimWorkflows] = useState<number>(50);
  const [simRps, setSimRps] = useState<number>(20.0);
  const [simSeed, setSimSeed] = useState<number>(42);
  const [simScenario, setSimScenario] = useState<string>('');
  const [simPersist, setSimPersist] = useState<boolean>(true);
  const [simGenerating, setSimGenerating] = useState<boolean>(false);
  const [simResult, setSimResult] = useState<SimulationGenerateResponse | null>(null);

  // Chaos Injection Form State
  const [chaosScenario, setChaosScenario] = useState<string>('payment_latency_degradation');
  const [chaosWorkflows, setChaosWorkflows] = useState<number>(30);
  const [chaosRps, setChaosRps] = useState<number>(20.0);
  const [chaosSeed, setChaosSeed] = useState<number>(777);
  const [chaosPersist, setChaosPersist] = useState<boolean>(true);
  const [chaosInjecting, setChaosInjecting] = useState<boolean>(false);
  const [chaosResult, setChaosResult] = useState<ChaosInjectionResponse | null>(null);

  const fetchScenarios = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await simulatorApi.listScenarios();
      setScenarios(list);
      if (list.length > 0) {
        setChaosScenario(list[0].scenario_type);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load chaos scenarios');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchScenarios();
  }, [fetchScenarios]);

  // Handle Simulation Generation
  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSimGenerating(true);
    setError(null);
    try {
      const res = await simulatorApi.generateSimulation({
        workflow_count: simWorkflows,
        arrival_rate_rps: simRps,
        seed: simSeed || null,
        incident_scenario: simScenario || null,
        persist_to_db: simPersist,
      });
      setSimResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation generation failed');
    } finally {
      setSimGenerating(false);
    }
  };

  // Handle Chaos Injection
  const handleInjectChaos = async (e: React.FormEvent) => {
    e.preventDefault();
    setChaosInjecting(true);
    setError(null);
    try {
      const res = await simulatorApi.injectChaos({
        scenario_type: chaosScenario,
        workflow_count: chaosWorkflows,
        arrival_rate_rps: chaosRps,
        seed: chaosSeed || null,
        persist_to_db: chaosPersist,
      });
      setChaosResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Chaos injection failed');
    } finally {
      setChaosInjecting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div>
        <h2 className="text-xl font-bold text-slate-100 tracking-tight font-mono">
          TraceSim Chaos Workbench & Simulation Console
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Generate deterministic synthetic distributed traces, inject targeted causal chaos experiments, and persist ground-truth incidents.
        </p>
      </div>

      <ErrorAlert error={error} />

      {/* Action Results Banner */}
      {simResult && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-slate-200 font-mono text-xs space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-emerald-400 font-bold">
              <CheckCircle2 className="h-4 w-4" />
              <span>Simulation Run Completed Successfully</span>
            </div>
            {onNavigateExecutions && (
              <button
                onClick={onNavigateExecutions}
                className="flex items-center space-x-1 text-emerald-400 hover:text-emerald-300 font-semibold"
              >
                <span>View Traces</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1 text-[11px]">
            <div>Workflows: <strong className="text-slate-100">{simResult.executions_generated}</strong></div>
            <div>Spans: <strong className="text-slate-100">{simResult.events_generated}</strong></div>
            <div>Error Rate: <strong className="text-slate-100">{simResult.summary_statistics.error_rate_percent.toFixed(1)}%</strong></div>
            <div>Wall Time: <strong className="text-slate-100">{simResult.generation_wall_time_ms.toFixed(1)}ms</strong></div>
          </div>
        </div>
      )}

      {chaosResult && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-slate-200 font-mono text-xs space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-rose-400 font-bold">
              <Flame className="h-4 w-4" />
              <span>Chaos Incident Injected: {chaosResult.scenario_type}</span>
            </div>
            {onNavigateExecutions && (
              <button
                onClick={onNavigateExecutions}
                className="flex items-center space-x-1 text-rose-400 hover:text-rose-300 font-semibold"
              >
                <span>Inspect Affected Traces</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          <p className="text-[11px] text-slate-300">
            <strong>Root Cause:</strong> {chaosResult.ground_truth_root_cause}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1 text-[11px]">
            <div>Total Runs: <strong className="text-slate-100">{chaosResult.total_executions}</strong></div>
            <div>Affected Runs: <strong className="text-rose-400 font-bold">{chaosResult.executions_affected}</strong></div>
            <div>Error Rate: <strong className="text-slate-100">{chaosResult.error_rate_percent.toFixed(1)}%</strong></div>
            <div>Mean Latency: <strong className="text-slate-100">{chaosResult.mean_latency_ms.toFixed(1)}ms</strong></div>
          </div>
        </div>
      )}

      {/* Control Workbench Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Panel A: Synthetic Trace Generator */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm shadow-xl font-mono text-xs space-y-4">
          <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
            <Zap className="h-4 w-4 text-emerald-400" />
            <h3 className="font-bold text-slate-100 text-sm">
              Synthetic Workload Trace Generator
            </h3>
          </div>

          <form onSubmit={handleGenerate} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-slate-400 block text-[11px] mb-1">Workflow Count</label>
                <input
                  type="number"
                  min="1"
                  max="1000"
                  value={simWorkflows}
                  onChange={(e) => setSimWorkflows(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100"
                />
              </div>
              <div>
                <label className="text-slate-400 block text-[11px] mb-1">Arrival Rate (RPS)</label>
                <input
                  type="number"
                  step="1"
                  value={simRps}
                  onChange={(e) => setSimRps(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-slate-400 block text-[11px] mb-1">Random Seed</label>
                <input
                  type="number"
                  value={simSeed}
                  onChange={(e) => setSimSeed(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100"
                />
              </div>
              <div>
                <label className="text-slate-400 block text-[11px] mb-1">Scenario (Optional)</label>
                <select
                  value={simScenario}
                  onChange={(e) => setSimScenario(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100"
                >
                  <option value="">None (Baseline)</option>
                  {scenarios.map((s) => (
                    <option key={s.scenario_type} value={s.scenario_type}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <label className="flex items-center space-x-2 pt-1 cursor-pointer select-none text-slate-300">
              <input
                type="checkbox"
                checked={simPersist}
                onChange={(e) => setSimPersist(e.target.checked)}
                className="rounded bg-slate-950 border-slate-700 text-emerald-500"
              />
              <span className="text-[11px]">Persist generated traces to PostgreSQL database</span>
            </label>

            <button
              type="submit"
              disabled={simGenerating}
              className="w-full py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-bold transition shadow-lg shadow-emerald-500/20 disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              <Play className={`h-4 w-4 ${simGenerating ? 'animate-spin' : ''}`} />
              <span>{simGenerating ? 'Simulating Workloads...' : 'Generate Trace Simulation'}</span>
            </button>
          </form>
        </div>

        {/* Panel B: Targeted Chaos Injection */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm shadow-xl font-mono text-xs space-y-4">
          <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
            <Flame className="h-4 w-4 text-rose-400" />
            <h3 className="font-bold text-slate-100 text-sm">
              Targeted Chaos Incident Injection
            </h3>
          </div>

          <form onSubmit={handleInjectChaos} className="space-y-3">
            <div>
              <label className="text-slate-400 block text-[11px] mb-1">Chaos Scenario Preset</label>
              <select
                value={chaosScenario}
                onChange={(e) => setChaosScenario(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100"
              >
                {scenarios.map((s) => (
                  <option key={s.scenario_type} value={s.scenario_type}>
                    {s.name} ({s.severity})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-3 gap-2.5">
              <div>
                <label className="text-slate-400 block text-[11px] mb-1">Workload</label>
                <input
                  type="number"
                  min="1"
                  max="500"
                  value={chaosWorkflows}
                  onChange={(e) => setChaosWorkflows(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100"
                />
              </div>
              <div>
                <label className="text-slate-400 block text-[11px] mb-1">Arrival RPS</label>
                <input
                  type="number"
                  value={chaosRps}
                  onChange={(e) => setChaosRps(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100"
                />
              </div>
              <div>
                <label className="text-slate-400 block text-[11px] mb-1">Random Seed</label>
                <input
                  type="number"
                  value={chaosSeed}
                  onChange={(e) => setChaosSeed(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100"
                />
              </div>
            </div>

            <label className="flex items-center space-x-2 pt-1 cursor-pointer select-none text-slate-300">
              <input
                type="checkbox"
                checked={chaosPersist}
                onChange={(e) => setChaosPersist(e.target.checked)}
                className="rounded bg-slate-950 border-slate-700 text-rose-500"
              />
              <span className="text-[11px]">Record and persist ground-truth incident</span>
            </label>

            <button
              type="submit"
              disabled={chaosInjecting}
              className="w-full py-2 rounded-lg bg-rose-500 hover:bg-rose-600 text-white font-bold transition shadow-lg shadow-rose-500/20 disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              <ShieldAlert className={`h-4 w-4 ${chaosInjecting ? 'animate-spin' : ''}`} />
              <span>{chaosInjecting ? 'Injecting Chaos Scenario...' : 'Inject Chaos Scenario'}</span>
            </button>
          </form>
        </div>
      </div>

      {/* Chaos Scenario Catalog Cards */}
      <div className="space-y-3 font-mono text-xs">
        <div className="flex items-center space-x-2">
          <Layers className="h-4 w-4 text-purple-400" />
          <h3 className="font-bold text-slate-100 text-sm">
            Causal Chaos Incident Catalog ({scenarios.length})
          </h3>
        </div>

        {loading && scenarios.length === 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {scenarios.map((s) => (
              <div
                key={s.scenario_type}
                className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-2.5 hover:border-slate-700 transition backdrop-blur-sm"
              >
                <div className="flex items-start justify-between">
                  <h4 className="font-bold text-slate-100 text-xs truncate">{s.name}</h4>
                  <Badge variant={s.severity === 'CRITICAL' ? 'danger' : 'warning'}>
                    {s.severity}
                  </Badge>
                </div>
                <p className="text-[11px] text-slate-400 line-clamp-2">{s.description}</p>
                <div className="pt-1.5 border-t border-slate-800 text-[10px] text-slate-500 space-y-1">
                  <div>Affected: <strong className="text-slate-300">{s.affected_services.join(', ')}</strong></div>
                  <div>Root Cause: <strong className="text-rose-400">{s.ground_truth_root_cause}</strong></div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
