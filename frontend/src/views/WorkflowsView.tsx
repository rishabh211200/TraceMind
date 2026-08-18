import React, { useEffect, useState, useCallback } from 'react';
import { workflowsApi } from '../api/workflows';
import { WorkflowDefinition } from '../types/workflow';
import { WorkflowDag } from '../components/graphs/WorkflowDag';
import { StatCard } from '../components/common/StatCard';
import { Badge } from '../components/common/Badge';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { SkeletonCard, SkeletonTable } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import {
  GitBranch,
  Activity,
  Clock,
  TrendingUp,
  RefreshCw,
  Layers,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';

interface WorkflowsViewProps {
  initialWorkflowId?: string | null;
  onNavigateExecution?: (executionId: string) => void;
}

export const WorkflowsView: React.FC<WorkflowsViewProps> = ({
  initialWorkflowId,
  onNavigateExecution,
}) => {
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>(
    initialWorkflowId || 'order_fulfillment'
  );
  const [activeWorkflow, setActiveWorkflow] = useState<WorkflowDefinition | null>(null);
  const [stats, setStats] = useState<any | null>(null);
  const [executions, setExecutions] = useState<any[]>([]);

  const [detailsLoading, setDetailsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch list of workflows
  const fetchWorkflows = useCallback(async () => {
    setError(null);
    try {
      const list = await workflowsApi.listWorkflows();
      const safeList = Array.isArray(list) ? list : [];
      setWorkflows(safeList);
      if (safeList.length > 0 && !selectedWorkflowId) {
        setSelectedWorkflowId(safeList[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workflows');
    }
  }, [selectedWorkflowId]);

  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  // Load details, DAG, stats, and executions for selected workflow
  const loadWorkflowDetails = useCallback(async (id: string) => {
    setSelectedWorkflowId(id);
    setDetailsLoading(true);
    try {
      const [wf, wfStats, execsRes] = await Promise.all([
        workflowsApi.getWorkflow(id).catch(() => null),
        workflowsApi.getWorkflowStats(id).catch(() => null),
        workflowsApi.listWorkflowExecutions(id, { limit: 10 }).catch(() => ({
          items: [],
          pagination: { total_count: 0, page: 1, limit: 10, total_pages: 1, has_next: false, has_prev: false },
        })),
      ]);
      setActiveWorkflow(wf);
      setStats(wfStats);
      const execItems = (execsRes as any)?.items || (execsRes as any)?.executions || (Array.isArray(execsRes) ? execsRes : []);
      setExecutions(execItems);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workflow details');
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedWorkflowId) {
      loadWorkflowDetails(selectedWorkflowId);
    }
  }, [selectedWorkflowId, loadWorkflowDetails]);

  const totalExecs = stats?.total_executions ?? 0;
  const succExecs = stats?.successful_executions ?? stats?.completed_executions ?? 0;
  const succRate = stats?.success_rate_percent ?? 100.0;
  const errRate = stats?.error_rate_percent ?? 0.0;
  const p50Dur = stats?.median_duration_ms ?? stats?.p50_duration_ms ?? 0.0;
  const meanDur = stats?.mean_duration_ms ?? 0.0;
  const p95Dur = stats?.p95_duration_ms ?? 0.0;
  const maxDur = stats?.max_duration_ms ?? 0.0;

  return (
    <div className="space-y-6">
      {/* Header and Workflow Selector Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 tracking-tight font-mono">
            Workflow Graph Explorer
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Topological DAG definition inspection, step dependencies, and runtime duration distributions.
          </p>
        </div>

        {/* Workflow Dropdown Selector */}
        <div className="flex items-center space-x-3">
          <label className="text-xs font-mono text-slate-400">Workflow:</label>
          <select
            value={selectedWorkflowId}
            onChange={(e) => setSelectedWorkflowId(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-emerald-500 transition"
          >
            {workflows.map((wf) => (
              <option key={wf.id} value={wf.id}>
                {wf.name} ({wf.id})
              </option>
            ))}
          </select>
          <button
            onClick={() => loadWorkflowDetails(selectedWorkflowId)}
            disabled={detailsLoading}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
          >
            <RefreshCw className={`h-4 w-4 ${detailsLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <ErrorAlert error={error} onRetry={() => loadWorkflowDetails(selectedWorkflowId)} />

      {/* Workflow Stats Overview */}
      {detailsLoading && !stats ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : stats ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Executions"
            value={totalExecs.toLocaleString()}
            subtitle={`${succExecs} completed successfully`}
            icon={Layers}
            iconColor="text-emerald-400"
          />
          <StatCard
            title="Success Rate"
            value={`${Number(succRate).toFixed(1)}%`}
            subtitle={`${Number(errRate).toFixed(1)}% failure rate`}
            icon={succRate >= 95 ? CheckCircle2 : AlertCircle}
            iconColor={succRate >= 95 ? 'text-emerald-400' : 'text-amber-400'}
            badge={succRate >= 95 ? 'Optimal' : 'Degraded'}
            badgeType={succRate >= 95 ? 'success' : 'warning'}
          />
          <StatCard
            title="P50 Duration"
            value={`${Number(p50Dur).toFixed(1)} ms`}
            subtitle={`Mean: ${Number(meanDur).toFixed(1)} ms`}
            icon={Clock}
            iconColor="text-sky-400"
          />
          <StatCard
            title="P95 Duration"
            value={`${Number(p95Dur).toFixed(1)} ms`}
            subtitle={`Max: ${Number(maxDur).toFixed(1)} ms`}
            icon={TrendingUp}
            iconColor="text-purple-400"
          />
        </div>
      ) : null}

      {/* DAG Topological Visualizer Canvas */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm shadow-xl space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <GitBranch className="h-4 w-4 text-emerald-400" />
            <h3 className="text-sm font-semibold text-slate-100 font-mono">
              Topological Step Graph: {activeWorkflow?.name || selectedWorkflowId}
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-400">
            {activeWorkflow?.nodes?.length || 0} Steps | {activeWorkflow?.edges?.length || 0} Transitions
          </span>
        </div>

        {activeWorkflow ? (
          <WorkflowDag workflow={activeWorkflow} />
        ) : (
          <div className="h-[360px] rounded-xl border border-slate-800 bg-slate-950 flex items-center justify-center text-slate-500 font-mono text-xs">
            Loading workflow DAG definition...
          </div>
        )}
      </div>

      {/* Workflow Executions Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Activity className="h-4 w-4 text-sky-400" />
            <h3 className="text-sm font-semibold text-slate-100 font-mono">
              Execution Runs ({executions.length})
            </h3>
          </div>
        </div>

        {detailsLoading && executions.length === 0 ? (
          <SkeletonTable rows={5} />
        ) : executions.length === 0 ? (
          <EmptyState
            title="No Executions Found"
            description={`No execution records found for workflow '${selectedWorkflowId}'.`}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-2.5 font-semibold">Execution ID</th>
                  <th className="pb-2.5 font-semibold">Started At (UTC)</th>
                  <th className="pb-2.5 font-semibold">Duration</th>
                  <th className="pb-2.5 font-semibold">Retries</th>
                  <th className="pb-2.5 font-semibold">Incident Tag</th>
                  <th className="pb-2.5 font-semibold text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {executions.map((exec: any) => {
                  const duration = exec.duration_ms ?? exec.total_latency_ms ?? 0;
                  return (
                    <tr
                      key={exec.id}
                      onClick={() => onNavigateExecution && onNavigateExecution(exec.id)}
                      className="hover:bg-slate-800/40 transition cursor-pointer"
                    >
                      <td className="py-2.5 font-semibold text-slate-100">{exec.id}</td>
                      <td className="py-2.5 text-slate-400">
                        {exec.started_at ? new Date(exec.started_at).toISOString().replace('T', ' ').slice(0, 19) : '-'}
                      </td>
                      <td className="py-2.5 font-semibold">{Number(duration).toFixed(1)} ms</td>
                      <td className="py-2.5">{exec.retry_count || 0}</td>
                      <td className="py-2.5">
                        {exec.is_incident_affected ? (
                          <Badge variant="danger">{exec.incident_id || 'affected'}</Badge>
                        ) : (
                          <span className="text-slate-500">None</span>
                        )}
                      </td>
                      <td className="py-2.5 text-right">
                        <Badge
                          variant={
                            exec.status === 'COMPLETED'
                              ? 'success'
                              : exec.status === 'TIMEOUT'
                              ? 'warning'
                              : 'danger'
                          }
                        >
                          {exec.status}
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
    </div>
  );
};
