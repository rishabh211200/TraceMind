import React, { useState, useEffect, useCallback } from 'react';
import {
  SearchCheck,
  Filter,
  RefreshCw,
  X,
  Target,
  BarChart3,
  Layers,
  ChevronRight,
  Sparkles,
  Percent,
} from 'lucide-react';
import { rootCauseApi } from '../api/rootCause';
import { RootCauseReport, RootCauseStats, RootCauseFilter } from '../types/rootCause';
import { CausalGraphVisualizer } from '../components/rca/CausalGraphVisualizer';

export const RootCauseView: React.FC = () => {
  const [reports, setReports] = useState<RootCauseReport[]>([]);
  const [stats, setStats] = useState<RootCauseStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedReport, setSelectedReport] = useState<RootCauseReport | null>(null);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 20;

  // Filter state
  const [filters, setFilters] = useState<RootCauseFilter>({
    workflow_definition_id: '',
    culprit_service: '',
    incident_category: '',
    min_confidence: undefined,
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [reportsRes, statsRes] = await Promise.all([
        rootCauseApi.listReports({
          workflow_definition_id: filters.workflow_definition_id || undefined,
          culprit_service: filters.culprit_service || undefined,
          incident_category: filters.incident_category || undefined,
          min_confidence: filters.min_confidence,
          page,
          page_size: pageSize,
        }),
        rootCauseApi.getStats(),
      ]);

      setReports(reportsRes.items || []);
      setTotal(reportsRes.pagination?.total_count ?? (reportsRes.pagination as unknown as { total: number })?.total ?? 0);
      setStats(statsRes);
    } catch (err) {
      console.error('Failed to load root cause data:', err);
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-red-500/20 to-amber-500/10 border border-red-500/30 text-red-400">
              <SearchCheck className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-100 tracking-tight">
                Root Cause Engine
              </h1>
              <p className="text-sm text-gray-400">
                Graph-based deterministic reasoning & causal dependency fault attribution
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-gray-800/80 hover:bg-gray-700/80 border border-gray-700 text-sm font-medium text-gray-200 transition-colors shadow-sm"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-red-400' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-gray-900/60 border border-gray-800 shadow-md">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Total Diagnoses</span>
            <Target className="w-4 h-4 text-red-400" />
          </div>
          <div className="text-2xl font-bold text-gray-100 font-mono">
            {stats?.total_diagnoses ?? 0}
          </div>
          <p className="text-xs text-gray-500 mt-1">Causal reports evaluated</p>
        </div>

        <div className="p-4 rounded-xl bg-gray-900/60 border border-gray-800 shadow-md">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Top Root Culprit</span>
            <Layers className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-lg font-bold text-amber-300 font-mono truncate">
            {stats && Object.keys(stats.by_culprit_service).length > 0
              ? Object.entries(stats.by_culprit_service)[0][0]
              : 'N/A'}
          </div>
          <p className="text-xs text-gray-500 mt-1">Most frequent failure origin</p>
        </div>

        <div className="p-4 rounded-xl bg-gray-900/60 border border-gray-800 shadow-md">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Mean Confidence</span>
            <Percent className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 font-mono">
            {stats ? `${(stats.mean_confidence * 100).toFixed(1)}%` : '0.0%'}
          </div>
          <p className="text-xs text-gray-500 mt-1">Diagnostic certainty</p>
        </div>

        <div className="p-4 rounded-xl bg-gray-900/60 border border-gray-800 shadow-md">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Incident Patterns</span>
            <BarChart3 className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-indigo-300 font-mono">
            {stats ? Object.keys(stats.by_category).length : 0}
          </div>
          <p className="text-xs text-gray-500 mt-1">Unique causal fault classes</p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="p-4 rounded-xl bg-gray-900/80 border border-gray-800/80 backdrop-blur shadow-md flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-xs font-medium text-gray-400 mr-2">
          <Filter className="w-4 h-4 text-red-400" />
          <span>Filters:</span>
        </div>

        {/* Workflow ID */}
        <input
          type="text"
          placeholder="Workflow ID..."
          value={filters.workflow_definition_id}
          onChange={(e) => {
            setFilters((prev) => ({ ...prev, workflow_definition_id: e.target.value }));
            setPage(1);
          }}
          className="px-3 py-1.5 rounded-lg bg-gray-950 border border-gray-800 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-red-500/50"
        />

        {/* Culprit Service */}
        <input
          type="text"
          placeholder="Culprit Service..."
          value={filters.culprit_service}
          onChange={(e) => {
            setFilters((prev) => ({ ...prev, culprit_service: e.target.value }));
            setPage(1);
          }}
          className="px-3 py-1.5 rounded-lg bg-gray-950 border border-gray-800 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-red-500/50"
        />

        {/* Incident Category Dropdown */}
        <select
          value={filters.incident_category}
          onChange={(e) => {
            setFilters((prev) => ({ ...prev, incident_category: e.target.value }));
            setPage(1);
          }}
          className="px-3 py-1.5 rounded-lg bg-gray-950 border border-gray-800 text-xs text-gray-200 focus:outline-none focus:border-red-500/50"
        >
          <option value="">All Incident Patterns</option>
          <option value="DATABASE_IOPS_SATURATION">Database IOPS Saturation</option>
          <option value="SERVICE_CRASH">Service Crash</option>
          <option value="CASCADING_RETRY_STORM">Cascading Retry Storm</option>
          <option value="NETWORK_TRANSIT_DELAY">Network Transit Delay</option>
          <option value="FLASH_TRAFFIC_OVERLOAD">Flash Traffic Overload</option>
          <option value="DEPENDENCY_TIMEOUT">Dependency Timeout</option>
          <option value="SYSTEMIC_LATENCY_DEGRADATION">Systemic Latency Degradation</option>
        </select>

        {/* Reset button */}
        {(filters.workflow_definition_id || filters.culprit_service || filters.incident_category) && (
          <button
            onClick={() => {
              setFilters({
                workflow_definition_id: '',
                culprit_service: '',
                incident_category: '',
                min_confidence: undefined,
              });
              setPage(1);
            }}
            className="px-2.5 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs text-gray-300 transition-colors"
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Reports Table */}
      <div className="rounded-xl bg-gray-900/60 border border-gray-800 shadow-md overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-950/80 border-b border-gray-800 text-gray-400 uppercase tracking-wider font-mono">
              <tr>
                <th className="py-3 px-4">Execution ID</th>
                <th className="py-3 px-4">Primary Culprit</th>
                <th className="py-3 px-4">Incident Pattern</th>
                <th className="py-3 px-4">Confidence</th>
                <th className="py-3 px-4">Causal Chain</th>
                <th className="py-3 px-4">Analyzed At</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60 text-gray-300 font-sans">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-500">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto text-red-400 mb-2" />
                    <span>Loading diagnostic root cause reports...</span>
                  </td>
                </tr>
              ) : reports.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-500">
                    No root cause reports found. Run a simulation or incident to diagnose executions.
                  </td>
                </tr>
              ) : (
                reports.map((report) => (
                  <tr
                    key={report.id}
                    className="hover:bg-gray-800/40 transition-colors cursor-pointer"
                    onClick={() => setSelectedReport(report)}
                  >
                    <td className="py-3 px-4 font-mono text-gray-200">
                      {report.execution_id}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2.5 py-1 rounded-full text-[11px] font-mono font-semibold bg-red-950/70 border border-red-500/50 text-red-300">
                        {report.culprit_service}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-gray-300 font-mono text-[11px]">
                        {report.incident_category}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-2 rounded-full bg-gray-800 overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-red-500 to-amber-400 rounded-full"
                            style={{ width: `${Math.min(100, report.confidence * 100)}%` }}
                          />
                        </div>
                        <span className="font-mono text-xs text-gray-200">
                          {(report.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-gray-400 max-w-xs truncate">
                      {report.causal_path && report.causal_path.length > 0
                        ? report.causal_path.join(' -> ')
                        : report.culprit_service}
                    </td>
                    <td className="py-3 px-4 text-gray-400 font-mono text-[11px]">
                      {new Date(report.analyzed_at).toLocaleTimeString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedReport(report);
                        }}
                        className="p-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination controls */}
        {total > pageSize && (
          <div className="p-3 bg-gray-950/80 border-t border-gray-800 flex items-center justify-between text-xs text-gray-400">
            <span>
              Showing {Math.min(total, (page - 1) * pageSize + 1)} to{' '}
              {Math.min(total, page * pageSize)} of {total} reports
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="px-2.5 py-1 rounded bg-gray-800 disabled:opacity-50 text-gray-300"
              >
                Previous
              </button>
              <button
                disabled={page * pageSize >= total}
                onClick={() => setPage((p) => p + 1)}
                className="px-2.5 py-1 rounded bg-gray-800 disabled:opacity-50 text-gray-300"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Slide-out Diagnostic Evidence Drawer */}
      {selectedReport && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-2xl h-full bg-gray-900 border-l border-gray-800 p-6 overflow-y-auto space-y-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-800 pb-4">
              <div>
                <span className="text-xs font-mono uppercase tracking-wider text-red-400">
                  Diagnosis Details
                </span>
                <h3 className="text-xl font-bold text-gray-100 font-mono">
                  {selectedReport.execution_id}
                </h3>
              </div>
              <button
                onClick={() => setSelectedReport(null)}
                className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-gray-200 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Causal Graph Propagation Visualizer */}
            <CausalGraphVisualizer
              causalPath={selectedReport.causal_path}
              culpritService={selectedReport.culprit_service}
              incidentCategory={selectedReport.incident_category}
              confidence={selectedReport.confidence}
            />

            {/* Supporting Evidence List */}
            <div className="space-y-3">
              <h4 className="text-sm font-semibold text-gray-200 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400" />
                <span>Quantitative Supporting Evidence</span>
              </h4>
              <div className="space-y-2">
                {selectedReport.supporting_evidence.map((evidence, i) => (
                  <div
                    key={i}
                    className="p-3 rounded-lg bg-gray-950/80 border border-gray-800/80 text-xs text-gray-300 flex items-start gap-2.5"
                  >
                    <span className="mt-1 w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />
                    <span className="leading-relaxed">{evidence}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Alternative Hypotheses */}
            {selectedReport.alternative_hypotheses && selectedReport.alternative_hypotheses.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-gray-200 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-indigo-400" />
                  <span>Ranked Alternative Hypotheses</span>
                </h4>
                <div className="space-y-2.5">
                  {selectedReport.alternative_hypotheses.map((alt, idx) => (
                    <div
                      key={alt.id || idx}
                      className="p-3.5 rounded-lg bg-gray-950/60 border border-gray-800 text-xs space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-gray-400 font-bold">#{idx + 2}</span>
                          <span className="font-mono font-semibold text-gray-200">
                            {alt.culprit_service}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-gray-800 text-gray-300">
                            {alt.incident_category}
                          </span>
                          <span className="font-mono font-bold text-amber-300">
                            {(alt.confidence * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>

                      {alt.supporting_evidence && alt.supporting_evidence.length > 0 && (
                        <p className="text-[11px] text-gray-400 italic">
                          "{alt.supporting_evidence[0]}"
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
