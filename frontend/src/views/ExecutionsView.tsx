import React, { useEffect, useState, useCallback } from 'react';
import { executionsApi, ExecutionFilterParams } from '../api/executions';
import {
  ExecutionListResponse,
  ExecutionSummary,
  TraceTreeNode,
} from '../types/execution';
import { TraceWaterfall } from '../components/waterfall/TraceWaterfall';
import { Badge } from '../components/common/Badge';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { SkeletonTable } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import {
  Filter,
  RefreshCw,
  Layers,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  Flame,
  X,
} from 'lucide-react';

interface ExecutionsViewProps {
  initialExecutionId?: string | null;
}

export const ExecutionsView: React.FC<ExecutionsViewProps> = ({ initialExecutionId }) => {
  const [data, setData] = useState<ExecutionListResponse | null>(null);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(
    initialExecutionId || null
  );
  const [activeExecution, setActiveExecution] = useState<ExecutionSummary | null>(null);
  const [traceTree, setTraceTree] = useState<TraceTreeNode | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [incidentOnly, setIncidentOnly] = useState<boolean>(false);
  const [workflowFilter, setWorkflowFilter] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const limit = 15;

  const [loading, setLoading] = useState<boolean>(true);
  const [treeLoading, setTreeLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchExecutions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: ExecutionFilterParams = {
        page,
        limit,
        status: statusFilter || undefined,
        workflow_id: workflowFilter || undefined,
        is_incident_affected: incidentOnly ? true : undefined,
      };
      const res = await executionsApi.listExecutions(params);
      setData(res);

      // Auto-select first execution if none selected
      if (!selectedExecutionId && res.items.length > 0) {
        setSelectedExecutionId(res.items[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load executions');
    } finally {
      setLoading(false);
    }
  }, [page, limit, statusFilter, workflowFilter, incidentOnly, selectedExecutionId]);

  useEffect(() => {
    fetchExecutions();
  }, [fetchExecutions]);

  // Fetch hierarchical trace tree when an execution is selected
  const loadTraceTree = useCallback(async (id: string) => {
    setSelectedExecutionId(id);
    setTreeLoading(true);
    try {
      const [exec, tree] = await Promise.all([
        executionsApi.getExecution(id).catch(() => null),
        executionsApi.getExecutionTree(id).catch(() => null),
      ]);
      setActiveExecution(exec);
      setTraceTree(tree);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load trace tree');
    } finally {
      setTreeLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedExecutionId) {
      loadTraceTree(selectedExecutionId);
    }
  }, [selectedExecutionId, loadTraceTree]);

  return (
    <div className="space-y-6">
      {/* Header and Filter Toolbar */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-100 tracking-tight font-mono">
              Execution Explorer & Distributed Trace Visualizer
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Multi-column execution search, causal root cause annotations, and hierarchical Gantt waterfall timelines.
            </p>
          </div>
          <button
            onClick={fetchExecutions}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition text-xs font-mono disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {/* Filter Controls Bar */}
        <div className="p-3.5 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm flex flex-wrap items-center gap-3 text-xs font-mono">
          <div className="flex items-center space-x-2">
            <Filter className="h-3.5 w-3.5 text-slate-400" />
            <span className="text-slate-400">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200"
            >
              <option value="">All Statuses</option>
              <option value="COMPLETED">COMPLETED</option>
              <option value="FAILED">FAILED</option>
              <option value="TIMEOUT">TIMEOUT</option>
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-slate-400">Workflow:</span>
            <input
              type="text"
              placeholder="e.g. order_fulfillment"
              value={workflowFilter}
              onChange={(e) => {
                setWorkflowFilter(e.target.value);
                setPage(1);
              }}
              className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 w-44 placeholder-slate-600"
            />
          </div>

          <label className="flex items-center space-x-2 cursor-pointer select-none text-slate-300 hover:text-slate-100">
            <input
              type="checkbox"
              checked={incidentOnly}
              onChange={(e) => {
                setIncidentOnly(e.target.checked);
                setPage(1);
              }}
              className="rounded bg-slate-950 border-slate-700 text-emerald-500 focus:ring-0"
            />
            <span>Incident Affected Only</span>
          </label>

          {(statusFilter || workflowFilter || incidentOnly) && (
            <button
              onClick={() => {
                setStatusFilter('');
                setWorkflowFilter('');
                setIncidentOnly(false);
                setPage(1);
              }}
              className="text-xs text-rose-400 hover:text-rose-300 transition flex items-center space-x-1 ml-auto"
            >
              <X className="h-3 w-3" />
              <span>Clear Filters</span>
            </button>
          )}
        </div>
      </div>

      <ErrorAlert error={error} onRetry={fetchExecutions} />

      {/* Main Content: Split Grid of Execution List & Trace Waterfall */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (5 Cols): Execution Selection Table */}
        <div className="lg:col-span-5 rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-sm shadow-xl space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
            <span className="font-semibold text-slate-200">
              Executions ({data?.pagination.total_count || 0})
            </span>
            <span className="text-slate-500">
              Page {data?.pagination.page || 1} of {data?.pagination.total_pages || 1}
            </span>
          </div>

          {loading && !data ? (
            <SkeletonTable rows={8} />
          ) : data?.items.length === 0 ? (
            <EmptyState
              title="No Executions Match Filter"
              description="Try adjusting your status or incident filter criteria."
            />
          ) : (
            <div className="space-y-1.5 max-h-[680px] overflow-y-auto pr-1">
              {data?.items.map((exec) => {
                const isSelected = selectedExecutionId === exec.id;
                return (
                  <div
                    key={exec.id}
                    onClick={() => setSelectedExecutionId(exec.id)}
                    className={`p-3 rounded-lg border transition cursor-pointer flex flex-col space-y-1.5 ${
                      isSelected
                        ? 'bg-slate-900 border-emerald-500/50 shadow-md ring-1 ring-emerald-500/20'
                        : 'bg-slate-950/70 border-slate-800/80 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-100 truncate">{exec.id}</span>
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
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>{exec.workflow_definition_id}</span>
                      <span><strong className="text-slate-200">{exec.duration_ms.toFixed(1)}ms</strong></span>
                    </div>

                    {exec.is_incident_affected && (
                      <div className="pt-1 flex items-center space-x-1 text-[10px] text-rose-400">
                        <Flame className="h-3 w-3" />
                        <span>Incident: {exec.incident_id || 'affected'}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Pagination Controls */}
          {data && data.pagination.total_pages > 1 && (
            <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-[11px]">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={!data.pagination.has_prev}
                className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-40 transition flex items-center space-x-1"
              >
                <ChevronLeft className="h-3 w-3" />
                <span>Prev</span>
              </button>
              <span className="text-slate-400">
                Page {data.pagination.page} / {data.pagination.total_pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(data.pagination.total_pages, p + 1))}
                disabled={!data.pagination.has_next}
                className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-40 transition flex items-center space-x-1"
              >
                <span>Next</span>
                <ChevronRight className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>

        {/* Right Column (7 Cols): Selected Trace Detail & Waterfall Visualizer */}
        <div className="lg:col-span-7 space-y-4">
          {activeExecution && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 backdrop-blur-sm shadow-xl font-mono text-xs space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-slate-500 text-[10px] uppercase">Selected Trace</span>
                  <h3 className="text-sm font-bold text-slate-100">{activeExecution.id}</h3>
                </div>
                <div className="flex items-center space-x-2">
                  <Badge
                    variant={
                      activeExecution.status === 'COMPLETED'
                        ? 'success'
                        : activeExecution.status === 'TIMEOUT'
                        ? 'warning'
                        : 'danger'
                    }
                    size="md"
                  >
                    {activeExecution.status}
                  </Badge>
                </div>
              </div>

              {/* Execution Summary Grid */}
              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-800 text-[11px]">
                <div>
                  <span className="text-slate-500 block">DURATION</span>
                  <span className="text-slate-100 font-bold">{activeExecution.duration_ms.toFixed(2)} ms</span>
                </div>
                <div>
                  <span className="text-slate-500 block">ERRORS / RETRIES</span>
                  <span className="text-slate-200">{activeExecution.error_count} errs / {activeExecution.retry_count} retries</span>
                </div>
                <div>
                  <span className="text-slate-500 block">STARTED (UTC)</span>
                  <span className="text-slate-300">{new Date(activeExecution.started_at).toISOString().slice(11, 23)}</span>
                </div>
              </div>

              {/* Failure / Root Cause Alert Banner */}
              {activeExecution.failure_reason && (
                <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-[11px] flex items-start space-x-2 mt-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400 mt-0.5" />
                  <div>
                    <span className="font-bold">Failure Reason:</span>
                    <p className="mt-0.5">{activeExecution.failure_reason}</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Trace Tree Gantt Waterfall Visualizer */}
          {treeLoading ? (
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-12 flex flex-col items-center justify-center text-slate-500 font-mono text-xs animate-pulse">
              <Layers className="h-6 w-6 text-slate-600 mb-2" />
              <span>Reconstructing trace waterfall timeline...</span>
            </div>
          ) : traceTree ? (
            <TraceWaterfall rootNode={traceTree} totalDurationMs={activeExecution?.duration_ms} />
          ) : (
            <EmptyState
              title="No Trace Tree Selected"
              description="Select an execution on the left to reconstruct its distributed trace waterfall."
            />
          )}
        </div>
      </div>
    </div>
  );
};
