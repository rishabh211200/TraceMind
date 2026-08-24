import React, { useEffect, useState, useCallback } from 'react';
import { executionsApi, ExecutionFilterParams } from '../api/executions';
import { predictionsApi } from '../api/predictions';
import { Prediction } from '../types/prediction';
import { TraceWaterfall } from '../components/waterfall/TraceWaterfall';
import { ShapAttributionDrawer } from '../components/waterfall/ShapAttributionDrawer';
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
  Flame,
  X,
  BrainCircuit,
} from 'lucide-react';

interface ExecutionsViewProps {
  initialExecutionId?: string | null;
}

export const ExecutionsView: React.FC<ExecutionsViewProps> = ({ initialExecutionId }) => {
  const [data, setData] = useState<any | null>(null);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(
    initialExecutionId || null
  );
  const [activeExecution, setActiveExecution] = useState<any | null>(null);
  const [traceTree, setTraceTree] = useState<any | null>(null);
  const [activePrediction, setActivePrediction] = useState<Prediction | null>(null);
  const [isShapDrawerOpen, setIsShapDrawerOpen] = useState<boolean>(false);

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
      const res: any = await executionsApi.listExecutions(params);
      setData(res);

      const items = res?.items || res?.executions || (Array.isArray(res) ? res : []);
      // Auto-select first execution if none selected
      if (!selectedExecutionId && items.length > 0) {
        setSelectedExecutionId(items[0].id);
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

  // Fetch hierarchical trace tree and ML prediction when an execution is selected
  const loadTraceTreeAndPrediction = useCallback(async (id: string) => {
    setSelectedExecutionId(id);
    setTreeLoading(true);
    try {
      const [exec, tree, preds] = await Promise.all([
        executionsApi.getExecution(id).catch(() => null),
        executionsApi.getExecutionTree(id).catch(() => null),
        predictionsApi.getExecutionPredictions(id).catch(() => []),
      ]);
      setActiveExecution(exec);
      setTraceTree(tree);
      if (Array.isArray(preds) && preds.length > 0) {
        setActivePrediction(preds[preds.length - 1]);
      } else {
        setActivePrediction(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load trace details');
    } finally {
      setTreeLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedExecutionId) {
      loadTraceTreeAndPrediction(selectedExecutionId);
    }
  }, [selectedExecutionId, loadTraceTreeAndPrediction]);

  const itemsList: any[] = data?.items || data?.executions || (Array.isArray(data) ? data : []);
  const totalCount = data?.pagination?.total_count ?? itemsList.length;
  const totalPages = data?.pagination?.total_pages ?? 1;
  const currentPage = data?.pagination?.page ?? page;

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-100 tracking-tight font-mono">
            Workflow Executions & Trace Waterfall
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Hierarchical span timeline analysis, in-flight ML failure predictions, and TreeSHAP explainability.
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

      <ErrorAlert error={error} onRetry={fetchExecutions} />

      {/* Multi-Column Search & Filter Bar */}
      <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm shadow-xl font-mono text-xs space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center space-x-2 text-slate-300 font-semibold">
            <Filter className="h-3.5 w-3.5 text-emerald-400" />
            <span>Search & Multi-Column Filters</span>
          </div>
          {(statusFilter || incidentOnly || workflowFilter) && (
            <button
              onClick={() => {
                setStatusFilter('');
                setIncidentOnly(false);
                setWorkflowFilter('');
              }}
              className="text-[11px] text-slate-500 hover:text-slate-300 flex items-center space-x-1 transition"
            >
              <X className="h-3 w-3" />
              <span>Clear Filters</span>
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-slate-400 block text-[10px] mb-1">Status Filter</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500 text-xs"
            >
              <option value="">All Statuses</option>
              <option value="COMPLETED">COMPLETED</option>
              <option value="FAILED">FAILED</option>
              <option value="TIMEOUT">TIMEOUT</option>
            </select>
          </div>

          <div>
            <label className="text-slate-400 block text-[10px] mb-1">Workflow ID</label>
            <input
              type="text"
              placeholder="e.g. order_fulfillment"
              value={workflowFilter}
              onChange={(e) => setWorkflowFilter(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500 text-xs"
            />
          </div>

          <div className="flex items-end">
            <label className="flex items-center space-x-2 cursor-pointer pb-2 text-slate-300">
              <input
                type="checkbox"
                checked={incidentOnly}
                onChange={(e) => setIncidentOnly(e.target.checked)}
                className="rounded border-slate-700 bg-slate-950 text-emerald-500 focus:ring-emerald-500 h-4 w-4"
              />
              <span className="text-xs flex items-center space-x-1">
                <Flame className="h-3.5 w-3.5 text-rose-400" />
                <span>Incident Affected Only</span>
              </span>
            </label>
          </div>
        </div>
      </div>

      {/* Main Grid: Executions List (5 cols) + Gantt Waterfall Visualizer (7 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (5 Cols): Execution Selection Table */}
        <div className="lg:col-span-5 rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-sm shadow-xl space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
            <span className="font-semibold text-slate-200">
              Executions ({totalCount})
            </span>
            <span className="text-slate-500">
              Page {currentPage} of {totalPages}
            </span>
          </div>

          {loading && itemsList.length === 0 ? (
            <SkeletonTable rows={8} />
          ) : itemsList.length === 0 ? (
            <EmptyState
              title="No Executions Match Filter"
              description="Try adjusting your status or incident filter criteria."
            />
          ) : (
            <div className="space-y-1.5 max-h-[680px] overflow-y-auto pr-1">
              {itemsList.map((exec: any) => {
                const isSelected = selectedExecutionId === exec.id;
                const duration = exec.duration_ms ?? exec.total_latency_ms ?? 0;
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
                      <span><strong className="text-slate-200">{Number(duration).toFixed(1)}ms</strong></span>
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
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-[11px]">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1}
                className="flex items-center space-x-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 transition"
              >
                <ChevronLeft className="h-3 w-3" />
                <span>Prev</span>
              </button>
              <span className="text-slate-400">
                {currentPage} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage >= totalPages}
                className="flex items-center space-x-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 transition"
              >
                <span>Next</span>
                <ChevronRight className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>

        {/* Right Column (7 Cols): Trace Gantt Waterfall Visualizer */}
        <div className="lg:col-span-7 space-y-4 font-mono text-xs">
          {treeLoading ? (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-8 flex flex-col items-center justify-center space-y-3 min-h-[500px]">
              <RefreshCw className="h-6 w-6 text-emerald-400 animate-spin" />
              <span className="text-slate-400">Reconstructing hierarchical DAG trace tree...</span>
            </div>
          ) : activeExecution && traceTree ? (
            <div className="space-y-4">
              {/* Execution Summary Banner with ML Prediction Risk */}
              <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/80 backdrop-blur-sm shadow-xl space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-bold text-slate-100">{activeExecution.id}</span>
                      <Badge
                        variant={
                          activeExecution.status === 'COMPLETED'
                            ? 'success'
                            : activeExecution.status === 'TIMEOUT'
                            ? 'warning'
                            : 'danger'
                        }
                      >
                        {activeExecution.status}
                      </Badge>
                    </div>
                    <span className="text-[11px] text-slate-400 block mt-0.5">
                      Workflow: {activeExecution.workflow_definition_id}
                    </span>
                  </div>

                  {/* ML Failure Prediction Badge & Button */}
                  {activePrediction && (
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => setIsShapDrawerOpen(true)}
                        className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-purple-500/15 hover:bg-purple-500/25 border border-purple-500/40 text-purple-300 transition shadow-sm"
                      >
                        <BrainCircuit className="h-4 w-4 text-purple-400" />
                        <span className="font-bold">
                          {(activePrediction.failure_probability * 100).toFixed(1)}% Risk ({activePrediction.predicted_risk_level})
                        </span>
                        <span className="text-[10px] text-purple-400 underline ml-1">TreeSHAP &rarr;</span>
                      </button>
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-6 pt-2 border-t border-slate-800/80 text-xs">
                  <div>
                    <span className="text-slate-500 block text-[10px]">TOTAL DURATION</span>
                    <span className="font-bold text-emerald-400">
                      {Number(activeExecution.duration_ms ?? activeExecution.total_latency_ms ?? 0).toFixed(1)} ms
                    </span>
                  </div>

                  {activePrediction && (
                    <div>
                      <span className="text-slate-500 block text-[10px]">FORECAST LATENCY</span>
                      <span className="font-bold text-sky-400">
                        {activePrediction.predicted_latency_ms.toFixed(1)} ms
                      </span>
                    </div>
                  )}

                  <div>
                    <span className="text-slate-500 block text-[10px]">RETRIES</span>
                    <span className="font-bold text-slate-200">
                      {activeExecution.retry_count || 0}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-500 block text-[10px]">ERRORS</span>
                    <span className="font-bold text-rose-400">
                      {activeExecution.error_count || 0}
                    </span>
                  </div>
                </div>
              </div>

              {/* Gantt Waterfall Visualizer Component */}
              <TraceWaterfall
                rootNode={traceTree}
                totalDurationMs={activeExecution.duration_ms ?? activeExecution.total_latency_ms ?? 100}
              />
            </div>
          ) : (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12 text-center text-slate-500 min-h-[500px] flex flex-col items-center justify-center space-y-2">
              <Layers className="h-8 w-8 text-slate-600" />
              <p>Select an execution from the list on the left to inspect its hierarchical Trace Gantt Waterfall.</p>
            </div>
          )}
        </div>
      </div>

      {/* TreeSHAP Feature Attribution Slide-Out Drawer */}
      {isShapDrawerOpen && (
        <ShapAttributionDrawer
          prediction={activePrediction}
          onClose={() => setIsShapDrawerOpen(false)}
        />
      )}
    </div>
  );
};
