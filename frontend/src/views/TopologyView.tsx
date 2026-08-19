import React, { useEffect, useState, useCallback } from 'react';
import { servicesApi } from '../api/services';
import {
  ServiceProfile,
  ServiceTopology,
} from '../types/service';
import { TopologyGraph } from '../components/graphs/TopologyGraph';
import { Badge } from '../components/common/Badge';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { SkeletonCard } from '../components/common/LoadingSkeleton';
import {
  Network,
  RefreshCw,
  Server,
  Clock,
  Activity,
  X,
  Check,
  Edit3,
} from 'lucide-react';

interface TopologyViewProps {
  initialServiceName?: string | null;
}

export const TopologyView: React.FC<TopologyViewProps> = ({ initialServiceName }) => {
  const [topology, setTopology] = useState<ServiceTopology | null>(null);
  const [selectedService, setSelectedService] = useState<string | null>(initialServiceName || null);
  const [serviceProfile, setServiceProfile] = useState<ServiceProfile | null>(null);
  const [latencyStats, setLatencyStats] = useState<any | null>(null);
  const [healthStats, setHealthStats] = useState<any | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [inspectorLoading, setInspectorLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Edit State for Inspector
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editCapacity, setEditCapacity] = useState<number>(200);
  const [editTimeout, setEditTimeout] = useState<number>(2000);
  const [editRetries, setEditRetries] = useState<number>(2);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);

  const fetchTopology = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await servicesApi.getTopology();
      setTopology(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load topology');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTopology();
  }, [fetchTopology]);

  const loadServiceDetails = useCallback(async (serviceName: string) => {
    setSelectedService(serviceName);
    setInspectorLoading(true);
    setSaveSuccess(false);
    setIsEditing(false);
    try {
      const [profile, latency, health] = await Promise.all([
        servicesApi.getService(serviceName).catch(() => null),
        servicesApi.getLatencyStats(serviceName).catch(() => null),
        servicesApi.getHealth(serviceName).catch(() => null),
      ]);
      setServiceProfile(profile);
      setLatencyStats(latency);
      setHealthStats(health);

      if (profile) {
        setEditCapacity(profile.capacity || 200);
        setEditTimeout(profile.timeout_ms || 2000);
        setEditRetries(profile.max_retries || 2);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to inspect service');
    } finally {
      setInspectorLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialServiceName) {
      loadServiceDetails(initialServiceName);
    }
  }, [initialServiceName, loadServiceDetails]);

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedService) return;
    try {
      const updated = await servicesApi.updateService(selectedService, {
        capacity: editCapacity,
        timeout_ms: editTimeout,
        max_retries: editRetries,
      });
      setServiceProfile(updated);
      setSaveSuccess(true);
      setIsEditing(false);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save config');
    }
  };

  const p50Val = latencyStats?.median_p50_latency_ms ?? latencyStats?.p50_latency_ms;
  const p90Val = latencyStats?.p90_latency_ms;
  const p95Val = latencyStats?.p95_latency_ms;
  const p99Val = latencyStats?.p99_latency_ms;

  const errRate =
    healthStats?.failure_rate_percent ??
    healthStats?.error_rate_percent ??
    (healthStats?.error_rate !== undefined ? healthStats.error_rate * 100 : 0);
  const totalEventsCount =
    healthStats?.total_events ?? healthStats?.total_calls ?? 0;
  const retryCount =
    healthStats?.retry_events ?? healthStats?.retry_count ?? 0;

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-100 tracking-tight font-mono">
            System Dependency Graph Topology
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Interactive topology visualizer illustrating inter-service dependencies, database/cache bindings, and gateway traffic.
          </p>
        </div>
        <button
          onClick={fetchTopology}
          disabled={loading}
          className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition text-xs font-mono disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Topology</span>
        </button>
      </div>

      <ErrorAlert error={error} onRetry={fetchTopology} />

      {/* Main Canvas & Inspector Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
        {/* Left 3 Cols: React Flow Canvas */}
        <div className="lg:col-span-3">
          {loading && !topology ? (
            <div className="w-full h-[620px] rounded-xl border border-slate-800 bg-slate-900/50 flex items-center justify-center animate-pulse">
              <span className="text-slate-500 font-mono text-xs">Loading topology nodes...</span>
            </div>
          ) : topology ? (
            <TopologyGraph
              topology={topology}
              onSelectService={loadServiceDetails}
              selectedServiceName={selectedService}
            />
          ) : null}
        </div>

        {/* Right 1 Col: Service Inspector Drawer */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-5 backdrop-blur-sm shadow-xl min-h-[620px] flex flex-col font-mono text-xs">
          {selectedService ? (
            <div className="space-y-4 flex-1">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center space-x-2">
                  <Server className="h-4 w-4 text-emerald-400" />
                  <h3 className="font-bold text-slate-100 text-sm truncate">{selectedService}</h3>
                </div>
                <button
                  onClick={() => setSelectedService(null)}
                  className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {saveSuccess && (
                <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-[11px] flex items-center space-x-1.5">
                  <Check className="h-3.5 w-3.5" />
                  <span>Configuration updated successfully!</span>
                </div>
              )}

              {inspectorLoading ? (
                <div className="space-y-3 pt-4">
                  <SkeletonCard />
                  <SkeletonCard />
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Service Profile Metadata */}
                  <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 space-y-2">
                    <div className="flex justify-between">
                      <span className="text-slate-500">TYPE</span>
                      <Badge variant="neutral">{serviceProfile?.service_type || 'service'}</Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">CAPACITY</span>
                      <span className="text-slate-200">{serviceProfile?.capacity || '-'} req/s</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">BASE LATENCY</span>
                      <span className="text-slate-200">{serviceProfile?.baseline_latency_ms || '-'} ms</span>
                    </div>
                  </div>

                  {/* Latency Percentiles */}
                  {latencyStats && (
                    <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between text-slate-400 font-semibold mb-1">
                        <span>Latency Percentiles</span>
                        <Clock className="h-3.5 w-3.5 text-sky-400" />
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-[11px]">
                        <div>P50: <strong className="text-slate-100">{p50Val !== undefined && p50Val !== null ? `${Number(p50Val).toFixed(1)}ms` : '-'}</strong></div>
                        <div>P90: <strong className="text-slate-100">{p90Val !== undefined && p90Val !== null ? `${Number(p90Val).toFixed(1)}ms` : '-'}</strong></div>
                        <div>P95: <strong className="text-slate-100">{p95Val !== undefined && p95Val !== null ? `${Number(p95Val).toFixed(1)}ms` : '-'}</strong></div>
                        <div>P99: <strong className="text-slate-100">{p99Val !== undefined && p99Val !== null ? `${Number(p99Val).toFixed(1)}ms` : '-'}</strong></div>
                      </div>
                    </div>
                  )}

                  {/* Operational Health Stats */}
                  {healthStats && (
                    <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between text-slate-400 font-semibold mb-1">
                        <span>Reliability & Errors</span>
                        <Activity className="h-3.5 w-3.5 text-amber-400" />
                      </div>
                      <div className="space-y-1 text-[11px]">
                        <div className="flex justify-between">
                          <span className="text-slate-400">Total Events:</span>
                          <span className="text-slate-100">{totalEventsCount.toLocaleString()}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Error Rate:</span>
                          <span className={Number(errRate) > 5 ? 'text-rose-400 font-bold' : 'text-slate-100'}>
                            {Number(errRate).toFixed(2)}%
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Retry Events:</span>
                          <span className="text-slate-100">{retryCount}</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Configuration Editor */}
                  {serviceProfile && (
                    <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-300 font-semibold">Tuning & Baseline</span>
                        <button
                          onClick={() => setIsEditing(!isEditing)}
                          className="flex items-center space-x-1 text-emerald-400 hover:text-emerald-300 transition"
                        >
                          <Edit3 className="h-3 w-3" />
                          <span>{isEditing ? 'Cancel' : 'Edit'}</span>
                        </button>
                      </div>

                      {isEditing ? (
                        <form onSubmit={handleSaveConfig} className="space-y-2.5 pt-1">
                          <div>
                            <label className="text-slate-400 block text-[10px]">Capacity (Req/s)</label>
                            <input
                              type="number"
                              value={editCapacity}
                              onChange={(e) => setEditCapacity(Number(e.target.value))}
                              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-100 focus:outline-none focus:border-emerald-500 text-xs"
                            />
                          </div>
                          <div>
                            <label className="text-slate-400 block text-[10px]">Timeout (ms)</label>
                            <input
                              type="number"
                              value={editTimeout}
                              onChange={(e) => setEditTimeout(Number(e.target.value))}
                              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-100 focus:outline-none focus:border-emerald-500 text-xs"
                            />
                          </div>
                          <div>
                            <label className="text-slate-400 block text-[10px]">Max Retries</label>
                            <input
                              type="number"
                              value={editRetries}
                              onChange={(e) => setEditRetries(Number(e.target.value))}
                              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-100 focus:outline-none focus:border-emerald-500 text-xs"
                            />
                          </div>
                          <button
                            type="submit"
                            className="w-full py-1.5 rounded bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-bold transition mt-2"
                          >
                            Save Parameters
                          </button>
                        </form>
                      ) : (
                        <div className="text-[11px] space-y-1 text-slate-400">
                          <div>Timeout: <strong className="text-slate-200">{serviceProfile.timeout_ms || '-'} ms</strong></div>
                          <div>Max Retries: <strong className="text-slate-200">{serviceProfile.max_retries || '-'}</strong></div>
                          <div>Backoff: <strong className="text-slate-200">{serviceProfile.retry_backoff_ms || '-'} ms</strong></div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 space-y-2">
              <Network className="h-8 w-8 text-slate-600" />
              <p className="text-xs">Click on any service node in the graph to inspect its telemetry and adjust parameters.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
