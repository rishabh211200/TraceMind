import React, { useEffect, useState, useCallback } from 'react';
import { servicesApi } from '../api/services';
import { ServiceProfile } from '../types/service';
import { StatCard } from '../components/common/StatCard';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { SkeletonCard } from '../components/common/LoadingSkeleton';
import {
  Server,
  Database,
  Zap,
  Clock,
  Activity,
  AlertTriangle,
  Sliders,
  Check,
  RefreshCw,
} from 'lucide-react';

interface ServicesViewProps {
  initialServiceName?: string | null;
}

export const ServicesView: React.FC<ServicesViewProps> = ({ initialServiceName }) => {
  const [services, setServices] = useState<ServiceProfile[]>([]);
  const [selectedService, setSelectedService] = useState<string>(
    initialServiceName || 'payment-service'
  );
  const [activeProfile, setActiveProfile] = useState<ServiceProfile | null>(null);
  const [latencyStats, setLatencyStats] = useState<any | null>(null);
  const [healthStats, setHealthStats] = useState<any | null>(null);

  // Form Edit State
  const [capacity, setCapacity] = useState<number>(200);
  const [timeoutMs, setTimeoutMs] = useState<number>(2000);
  const [maxRetries, setMaxRetries] = useState<number>(2);
  const [baselineLatency, setBaselineLatency] = useState<number>(50);

  const [loading, setLoading] = useState<boolean>(true);
  const [detailsLoading, setDetailsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);

  const fetchServices = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await servicesApi.listServices();
      setServices(list);
      if (list.length > 0 && !selectedService) {
        setSelectedService(list[0].name);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to list services');
    } finally {
      setLoading(false);
    }
  }, [selectedService]);

  useEffect(() => {
    fetchServices();
  }, [fetchServices]);

  const loadServiceDetails = useCallback(async (name: string) => {
    setSelectedService(name);
    setDetailsLoading(true);
    setSaveSuccess(false);
    try {
      const [profile, latency, health] = await Promise.all([
        servicesApi.getService(name).catch(() => null),
        servicesApi.getLatencyStats(name).catch(() => null),
        servicesApi.getHealth(name).catch(() => null),
      ]);
      setActiveProfile(profile);
      setLatencyStats(latency);
      setHealthStats(health);

      if (profile) {
        setCapacity(profile.capacity || 200);
        setTimeoutMs(profile.timeout_ms || 2000);
        setMaxRetries(profile.max_retries || 2);
        setBaselineLatency(profile.baseline_latency_ms || 50);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load service details');
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedService) {
      loadServiceDetails(selectedService);
    }
  }, [selectedService, loadServiceDetails]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedService) return;
    try {
      const updated = await servicesApi.updateService(selectedService, {
        capacity,
        timeout_ms: timeoutMs,
        max_retries: maxRetries,
        baseline_latency_ms: baselineLatency,
      });
      setActiveProfile(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update service profile');
    }
  };

  const getServiceIcon = (type: string = '') => {
    if (type.includes('database')) return <Database className="h-4 w-4 text-amber-400" />;
    if (type.includes('cache')) return <Zap className="h-4 w-4 text-purple-400" />;
    return <Server className="h-4 w-4 text-emerald-400" />;
  };

  const p50Val = latencyStats?.median_p50_latency_ms ?? latencyStats?.p50_latency_ms;
  const p95Val = latencyStats?.p95_latency_ms;
  const p90Val = latencyStats?.p90_latency_ms;
  const p99Val = latencyStats?.p99_latency_ms;
  const minVal = latencyStats?.min_latency_ms;
  const maxVal = latencyStats?.max_latency_ms;
  const meanVal = latencyStats?.mean_latency_ms;
  const errRateVal = healthStats?.failure_rate_percent ?? healthStats?.error_rate_percent ?? (healthStats?.error_rate !== undefined ? healthStats.error_rate * 100 : 0);

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-100 tracking-tight font-mono">
            Service Observability & Latency Distributions
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Microservice baseline performance profiles, database-side latency percentiles (P50..P99), and live capacity tuning.
          </p>
        </div>
        <button
          onClick={() => loadServiceDetails(selectedService)}
          disabled={detailsLoading}
          className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition text-xs font-mono disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${detailsLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      <ErrorAlert error={error} onRetry={() => loadServiceDetails(selectedService)} />

      {/* Main Grid: Service Selection Sidebar + Detailed Metrics & Config */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (4 Cols): Services Navigation Cards */}
        <div className="lg:col-span-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-sm shadow-xl space-y-2.5 font-mono text-xs">
          <div className="border-b border-slate-800 pb-2 flex items-center justify-between text-slate-400 font-semibold">
            <span>Services Registry ({services.length})</span>
            <span className="text-[10px]">Click to inspect</span>
          </div>

          <div className="space-y-1.5 max-h-[640px] overflow-y-auto pr-1">
            {loading && services.length === 0 ? (
              <div className="space-y-2">
                <SkeletonCard />
                <SkeletonCard />
              </div>
            ) : (
              services.map((svc) => {
                const isSelected = selectedService === svc.name;
                return (
                  <div
                    key={svc.name}
                    onClick={() => setSelectedService(svc.name)}
                    className={`p-3 rounded-lg border transition cursor-pointer flex items-center justify-between ${
                      isSelected
                        ? 'bg-slate-900 border-emerald-500/50 shadow-md ring-1 ring-emerald-500/20'
                        : 'bg-slate-950/70 border-slate-800/80 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center space-x-2.5 overflow-hidden">
                      <div className="p-1.5 rounded bg-slate-800 border border-slate-700">
                        {getServiceIcon(svc.service_type)}
                      </div>
                      <div className="overflow-hidden">
                        <p className="font-semibold text-slate-100 truncate">{svc.name}</p>
                        <span className="text-[10px] text-slate-500 block truncate">
                          {svc.service_type}
                        </span>
                      </div>
                    </div>
                    <div className="text-right text-[11px] text-slate-400">
                      <div>{svc.baseline_latency_ms}ms</div>
                      <span className="text-[10px] text-slate-500">cap {svc.capacity}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column (8 Cols): Detailed Telemetry & Tuning */}
        <div className="lg:col-span-8 space-y-6">
          {activeProfile && (
            <div className="flex items-center justify-between text-xs font-mono text-slate-400">
              <span>Service Type: <strong className="text-slate-200">{activeProfile.service_type}</strong></span>
              <span>Dependencies: <strong className="text-slate-200">{activeProfile.dependencies?.length || 0}</strong></span>
            </div>
          )}

          {saveSuccess && (
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center space-x-2">
              <Check className="h-4 w-4" />
              <span>Service performance configuration successfully updated in database!</span>
            </div>
          )}

          {/* Metric Cards Grid */}
          {detailsLoading && !latencyStats ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <StatCard
                title="P50 Median Latency"
                value={p50Val !== undefined && p50Val !== null ? `${Number(p50Val).toFixed(1)} ms` : '-'}
                subtitle={`Mean: ${meanVal !== undefined && meanVal !== null ? `${Number(meanVal).toFixed(1)} ms` : '-'}`}
                icon={Clock}
                iconColor="text-emerald-400"
              />
              <StatCard
                title="P95 Tail Latency"
                value={p95Val !== undefined && p95Val !== null ? `${Number(p95Val).toFixed(1)} ms` : '-'}
                subtitle={`P99: ${p99Val !== undefined && p99Val !== null ? `${Number(p99Val).toFixed(1)} ms` : '-'}`}
                icon={Activity}
                iconColor="text-purple-400"
              />
              <StatCard
                title="Error / Failure Rate"
                value={`${Number(errRateVal || 0).toFixed(2)}%`}
                subtitle={`${healthStats?.failed_events || healthStats?.failure_count || healthStats?.error_count || 0} failed / ${healthStats?.total_events || healthStats?.total_calls || 0} total`}
                icon={AlertTriangle}
                iconColor={
                  Number(errRateVal || 0) > 5 ? 'text-rose-400' : 'text-amber-400'
                }
              />
            </div>
          )}

          {/* Latency Percentile Distribution Card */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm shadow-xl font-mono text-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <Clock className="h-4 w-4 text-sky-400" />
                <h3 className="font-bold text-slate-100 text-sm">
                  Latency Percentile Distribution (Database Aggregation)
                </h3>
              </div>
              <span className="text-slate-400 text-[11px]">
                {latencyStats?.count?.toLocaleString() || 0} span records
              </span>
            </div>

            {latencyStats ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
                <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">MIN</span>
                  <span className="text-slate-200 font-bold text-sm">
                    {minVal !== undefined && minVal !== null ? `${Number(minVal).toFixed(1)}ms` : '-'}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">P50 (MEDIAN)</span>
                  <span className="text-emerald-400 font-bold text-sm">
                    {p50Val !== undefined && p50Val !== null ? `${Number(p50Val).toFixed(1)}ms` : '-'}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">P90</span>
                  <span className="text-sky-400 font-bold text-sm">
                    {p90Val !== undefined && p90Val !== null ? `${Number(p90Val).toFixed(1)}ms` : '-'}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">P95</span>
                  <span className="text-amber-400 font-bold text-sm">
                    {p95Val !== undefined && p95Val !== null ? `${Number(p95Val).toFixed(1)}ms` : '-'}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">P99</span>
                  <span className="text-purple-400 font-bold text-sm">
                    {p99Val !== undefined && p99Val !== null ? `${Number(p99Val).toFixed(1)}ms` : '-'}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">MAX</span>
                  <span className="text-rose-400 font-bold text-sm">
                    {maxVal !== undefined && maxVal !== null ? `${Number(maxVal).toFixed(1)}ms` : '-'}
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-slate-500 py-4 text-center">No latency telemetry recorded for this service.</p>
            )}
          </div>

          {/* Configuration Tuning Form */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm shadow-xl font-mono text-xs space-y-4">
            <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
              <Sliders className="h-4 w-4 text-emerald-400" />
              <h3 className="font-bold text-slate-100 text-sm">
                Service Baseline & Concurrency Tuning
              </h3>
            </div>

            <form onSubmit={handleSave} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-slate-400 block text-[11px] mb-1">
                  Concurrency Capacity (Requests/sec)
                </label>
                <input
                  type="number"
                  value={capacity}
                  onChange={(e) => setCapacity(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="text-slate-400 block text-[11px] mb-1">
                  Baseline Latency (ms)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={baselineLatency}
                  onChange={(e) => setBaselineLatency(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="text-slate-400 block text-[11px] mb-1">
                  Client Timeout Limit (ms)
                </label>
                <input
                  type="number"
                  value={timeoutMs}
                  onChange={(e) => setTimeoutMs(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="text-slate-400 block text-[11px] mb-1">
                  Max Retry Budget
                </label>
                <input
                  type="number"
                  value={maxRetries}
                  onChange={(e) => setMaxRetries(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="sm:col-span-2 pt-2">
                <button
                  type="submit"
                  className="px-5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-bold transition shadow-lg shadow-emerald-500/20"
                >
                  Save Configuration
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
