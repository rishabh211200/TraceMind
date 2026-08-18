import React, { useEffect, useState, useCallback } from 'react';
import { servicesApi } from '../api/services';
import { executionsApi } from '../api/executions';
import { incidentsApi } from '../api/incidents';
import { ServiceHealthSummary } from '../types/service';
import { ExecutionSummary } from '../types/execution';
import { Incident } from '../types/incident';
import { StatCard } from '../components/common/StatCard';
import { Badge } from '../components/common/Badge';
import { SkeletonCard, SkeletonTable } from '../components/common/LoadingSkeleton';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import {
  Activity,
  AlertTriangle,
  Clock,
  Layers,
  RefreshCw,
  Server,
  TrendingUp,
  Flame,
} from 'lucide-react';

interface OverviewViewProps {
  onNavigateTab?: (tab: string, context?: Record<string, unknown>) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({ onNavigateTab }) => {
  const [telemetry, setTelemetry] = useState<ServiceHealthSummary[] | Record<string, ServiceHealthSummary>>([]);
  const [executions, setExecutions] = useState<ExecutionSummary[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [telemetryRes, execRes, incRes] = await Promise.all([
        servicesApi.getTelemetrySummary().catch(() => []),
        executionsApi.listExecutions({ limit: 10 }).catch(() => ({ items: [], pagination: { total_count: 0, page: 1, limit: 10, total_pages: 1, has_next: false, has_prev: false } })),
        incidentsApi.listIncidents().catch(() => []),
      ]);
      setTelemetry(telemetryRes);
      setExecutions(execRes.items || []);
      setIncidents(incRes || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load telemetry overview');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Aggregate metrics calculation
  const servicesList: ServiceHealthSummary[] = Array.isArray(telemetry)
    ? telemetry
    : Object.values(telemetry || {});
  const totalEvents = servicesList.reduce((acc, s) => acc + (s.total_events || 0), 0);
  const totalErrors = servicesList.reduce((acc, s) => acc + (s.error_count || 0), 0);
  const avgErrorRate = totalEvents > 0 ? (totalErrors / totalEvents) * 100 : 0.0;
  const avgLatency =
    servicesList.length > 0
      ? servicesList.reduce((acc, s) => acc + (s.mean_latency_ms || 0), 0) / servicesList.length
      : 0.0;
  const maxP95 =
    servicesList.length > 0
      ? Math.max(...servicesList.map((s) => s.p95_latency_ms || 0))
      : 0.0;

  return (
    <div className="space-y-6">
      {/* Header Bar with Refresh Button */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-100 tracking-tight font-mono">
            System Telemetry & Operations Overview
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time aggregate health, operational metrics, and incident intelligence across microservices.
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition text-xs font-mono disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Data</span>
        </button>
      </div>

      {/* Error Alert */}
      <ErrorAlert error={error} onRetry={fetchData} />

      {/* KPI Stats Grid */}
      {loading && Object.keys(telemetry).length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <StatCard
            title="Total Trace Events"
            value={totalEvents.toLocaleString()}
            subtitle="Span telemetry ingested"
            icon={Activity}
            iconColor="text-emerald-400"
            badge="Live DB"
            badgeType="success"
          />
          <StatCard
            title="Avg Error Rate"
            value={`${avgErrorRate.toFixed(2)}%`}
            subtitle={`${totalErrors} failures recorded`}
            icon={AlertTriangle}
            iconColor={avgErrorRate > 5 ? 'text-rose-400' : 'text-amber-400'}
            badge={avgErrorRate > 5 ? 'Elevated' : 'Normal'}
            badgeType={avgErrorRate > 5 ? 'danger' : 'success'}
          />
          <StatCard
            title="Mean Service Latency"
            value={`${avgLatency.toFixed(1)} ms`}
            subtitle="Across all microservices"
            icon={Clock}
            iconColor="text-sky-400"
          />
          <StatCard
            title="Max P95 Latency"
            value={`${maxP95.toFixed(1)} ms`}
            subtitle="Tail latency threshold"
            icon={TrendingUp}
            iconColor="text-purple-400"
          />
          <StatCard
            title="Recorded Incidents"
            value={incidents.length}
            subtitle="Causal chaos scenarios"
            icon={Flame}
            iconColor={incidents.length > 0 ? 'text-rose-400' : 'text-slate-400'}
            badge={incidents.length > 0 ? 'Ground Truth' : 'Clear'}
            badgeType={incidents.length > 0 ? 'danger' : 'info'}
          />
        </div>
      )}

      {/* Service Health Summary Table & Recent Incidents Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: System-wide Service Telemetry Summary */}
        <div className="lg:col-span-2 rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <Server className="h-4 w-4 text-emerald-400" />
              <h3 className="text-sm font-semibold text-slate-100 font-mono">
                Microservice Health & Reliability Summary
              </h3>
            </div>
            {onNavigateTab && (
              <button
                onClick={() => onNavigateTab('topology')}
                className="text-xs text-emerald-400 hover:text-emerald-300 font-mono transition"
              >
                View Topology &rarr;
              </button>
            )}
          </div>

          {loading && servicesList.length === 0 ? (
            <SkeletonTable rows={6} />
          ) : servicesList.length === 0 ? (
            <EmptyState
              title="No Service Telemetry Data"
              description="No telemetry events found in the database. Run a synthetic simulation to generate distributed workflow traces."
              actionText="Open Simulator Console"
              onAction={() => onNavigateTab && onNavigateTab('simulator')}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="pb-2.5 font-semibold">Service Name</th>
                    <th className="pb-2.5 font-semibold">Events</th>
                    <th className="pb-2.5 font-semibold">Error Rate</th>
                    <th className="pb-2.5 font-semibold">Mean Latency</th>
                    <th className="pb-2.5 font-semibold">P95 Latency</th>
                    <th className="pb-2.5 font-semibold text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {servicesList.map((svc) => {
                    const isHighError = svc.error_rate_percent > 5;
                    const isDegraded = svc.error_rate_percent > 0 || svc.p95_latency_ms > 200;

                    return (
                      <tr
                        key={svc.service}
                        className="hover:bg-slate-800/40 transition cursor-pointer"
                        onClick={() =>
                          onNavigateTab &&
                          onNavigateTab('services', { serviceName: svc.service })
                        }
                      >
                        <td className="py-2.5 font-semibold text-slate-100 flex items-center space-x-2">
                          <span className="h-2 w-2 rounded-full bg-emerald-400" />
                          <span>{svc.service}</span>
                        </td>
                        <td className="py-2.5">{svc.total_events.toLocaleString()}</td>
                        <td className="py-2.5">
                          <span className={isHighError ? 'text-rose-400 font-bold' : ''}>
                            {svc.error_rate_percent.toFixed(2)}%
                          </span>
                        </td>
                        <td className="py-2.5">{svc.mean_latency_ms.toFixed(1)} ms</td>
                        <td className="py-2.5">{svc.p95_latency_ms.toFixed(1)} ms</td>
                        <td className="py-2.5 text-right">
                          <Badge
                            variant={isHighError ? 'danger' : isDegraded ? 'warning' : 'success'}
                          >
                            {isHighError ? 'CRITICAL' : isDegraded ? 'DEGRADED' : 'HEALTHY'}
                          </Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Column: Ground-Truth Incidents & Recent Executions */}
        <div className="space-y-6">
          {/* Recent Ground-Truth Incidents */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm shadow-xl">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                <Flame className="h-4 w-4 text-rose-400" />
                <h3 className="text-sm font-semibold text-slate-100 font-mono">
                  Chaos Incidents
                </h3>
              </div>
              <span className="text-xs font-mono text-slate-400">{incidents.length} active</span>
            </div>

            {incidents.length === 0 ? (
              <p className="text-xs text-slate-400 font-mono py-4 text-center">
                No active chaos incidents recorded.
              </p>
            ) : (
              <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
                {incidents.slice(0, 4).map((inc) => (
                  <div
                    key={inc.id}
                    className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 text-xs font-mono space-y-1 hover:border-slate-700 transition"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-rose-300 truncate">{inc.scenario_type}</span>
                      <Badge variant={inc.severity === 'CRITICAL' ? 'danger' : 'warning'}>
                        {inc.severity}
                      </Badge>
                    </div>
                    <p className="text-[11px] text-slate-400 line-clamp-2">{inc.description}</p>
                    <div className="text-[10px] text-slate-500 pt-1 flex items-center justify-between">
                      <span>Affected: {inc.affected_services.join(', ')}</span>
                      <span>{inc.duration_seconds.toFixed(0)}s</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Quick Recent Executions Feed */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm shadow-xl">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                <Layers className="h-4 w-4 text-sky-400" />
                <h3 className="text-sm font-semibold text-slate-100 font-mono">
                  Recent Executions
                </h3>
              </div>
              {onNavigateTab && (
                <button
                  onClick={() => onNavigateTab('executions')}
                  className="text-xs text-sky-400 hover:text-sky-300 font-mono transition"
                >
                  All &rarr;
                </button>
              )}
            </div>

            {executions.length === 0 ? (
              <p className="text-xs text-slate-400 font-mono py-4 text-center">
                No recent executions found.
              </p>
            ) : (
              <div className="space-y-2">
                {executions.slice(0, 4).map((e) => (
                  <div
                    key={e.id}
                    onClick={() =>
                      onNavigateTab && onNavigateTab('executions', { executionId: e.id })
                    }
                    className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80 flex items-center justify-between text-xs font-mono hover:border-emerald-500/40 cursor-pointer transition"
                  >
                    <div>
                      <span className="font-semibold text-slate-200">{e.id}</span>
                      <span className="text-[10px] text-slate-500 block">
                        {e.workflow_definition_id}
                      </span>
                    </div>
                    <div className="text-right flex items-center space-x-2">
                      <span className="text-slate-400">{e.duration_ms.toFixed(1)}ms</span>
                      <Badge
                        variant={
                          e.status === 'COMPLETED'
                            ? 'success'
                            : e.status === 'TIMEOUT'
                            ? 'warning'
                            : 'danger'
                        }
                      >
                        {e.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
