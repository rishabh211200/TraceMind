import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Flame,
  Activity,
  GitBranch,
  RefreshCw,
  Search,
  Filter,
  Eye,
  X,
  Clock,
  Server,
  Zap,
  CheckCircle2,
} from 'lucide-react';
import { anomaliesApi } from '../api/anomalies';
import { Anomaly, AnomalyStats } from '../types/anomaly';

export const AnomaliesView: React.FC = () => {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [stats, setStats] = useState<AnomalyStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [calibrating, setCalibrating] = useState<boolean>(false);
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedAnomaly, setSelectedAnomaly] = useState<Anomaly | null>(null);
  const [calibrateSuccess, setCalibrateSuccess] = useState<boolean>(false);

  const fetchAnomalies = async () => {
    try {
      setLoading(true);
      const [listRes, statsRes] = await Promise.all([
        anomaliesApi.listAnomalies({
          anomaly_type: typeFilter || undefined,
          severity: severityFilter || undefined,
          page_size: 100,
        }),
        anomaliesApi.getStats(),
      ]);
      setAnomalies(listRes.items || []);
      setStats(statsRes);
    } catch (err) {
      console.error('Failed fetching anomalies:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnomalies();
  }, [typeFilter, severityFilter]);

  const handleRecalibrate = async () => {
    try {
      setCalibrating(true);
      await anomaliesApi.fit(120);
      setCalibrateSuccess(true);
      setTimeout(() => setCalibrateSuccess(false), 4000);
      await fetchAnomalies();
    } catch (err) {
      console.error('Failed to recalibrate:', err);
    } finally {
      setCalibrating(false);
    }
  };

  const filteredAnomalies = anomalies.filter((a) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      a.execution_id.toLowerCase().includes(query) ||
      a.anomaly_type.toLowerCase().includes(query) ||
      a.explanation.toLowerCase().includes(query) ||
      a.affected_services.some((s) => s.toLowerCase().includes(query))
    );
  });

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">
            <Flame className="w-3 h-3 mr-1" />
            CRITICAL
          </span>
        );
      case 'WARNING':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30">
            <AlertTriangle className="w-3 h-3 mr-1" />
            WARNING
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30">
            <Activity className="w-3 h-3 mr-1" />
            INFO
          </span>
        );
    }
  };

  const getAnomalyTypeIcon = (type: string) => {
    switch (type) {
      case 'LATENCY_SPIKE':
        return <Activity className="w-4 h-4 text-amber-400" />;
      case 'UNUSUAL_PATH':
        return <GitBranch className="w-4 h-4 text-purple-400" />;
      case 'RETRY_STORM':
        return <RefreshCw className="w-4 h-4 text-rose-400" />;
      case 'ERROR_CASCADE':
        return <Flame className="w-4 h-4 text-rose-500" />;
      case 'DEPENDENCY_TIMEOUT':
        return <Clock className="w-4 h-4 text-red-400" />;
      default:
        return <AlertTriangle className="w-4 h-4 text-blue-400" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-slate-900/60 p-6 rounded-xl border border-slate-800/80 backdrop-blur-sm shadow-xl">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-amber-400" />
            Unsupervised Anomaly Explorer
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Real-time multi-model anomaly detection across Isolation Forests, robust latency percentiles, and DAG transition paths.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {calibrateSuccess && (
            <span className="text-xs text-emerald-400 flex items-center gap-1 bg-emerald-950/50 border border-emerald-800/50 px-3 py-1.5 rounded-lg">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Baselines Calibrated
            </span>
          )}
          <button
            onClick={handleRecalibrate}
            disabled={calibrating}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 border border-slate-700 rounded-lg text-sm font-medium transition-all shadow-md active:scale-95"
          >
            <RefreshCw className={`w-4 h-4 ${calibrating ? 'animate-spin text-amber-400' : ''}`} />
            {calibrating ? 'Calibrating Baselines...' : 'Recalibrate Baselines'}
          </button>
        </div>
      </div>

      {/* Metric Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/50 p-5 rounded-xl border border-slate-800 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wider text-slate-400 font-medium">Total Anomalies</p>
            <p className="text-2xl font-bold text-slate-100 mt-1">{stats?.total_anomalies ?? anomalies.length}</p>
          </div>
          <div className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
            <Activity className="w-6 h-6 text-blue-400" />
          </div>
        </div>

        <div className="bg-slate-900/50 p-5 rounded-xl border border-slate-800 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wider text-rose-400 font-medium">Critical Outliers</p>
            <p className="text-2xl font-bold text-rose-400 mt-1">{stats?.by_severity?.CRITICAL ?? 0}</p>
          </div>
          <div className="p-3 bg-rose-500/10 rounded-lg border border-rose-500/20">
            <Flame className="w-6 h-6 text-rose-400" />
          </div>
        </div>

        <div className="bg-slate-900/50 p-5 rounded-xl border border-slate-800 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wider text-amber-400 font-medium">Warning Anomalies</p>
            <p className="text-2xl font-bold text-amber-400 mt-1">{stats?.by_severity?.WARNING ?? 0}</p>
          </div>
          <div className="p-3 bg-amber-500/10 rounded-lg border border-amber-500/20">
            <AlertTriangle className="w-6 h-6 text-amber-400" />
          </div>
        </div>

        <div className="bg-slate-900/50 p-5 rounded-xl border border-slate-800 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wider text-purple-400 font-medium">Anomaly Classes</p>
            <p className="text-2xl font-bold text-purple-400 mt-1">
              {stats ? Object.keys(stats.by_type).length : 5} Types
            </p>
          </div>
          <div className="p-3 bg-purple-500/10 rounded-lg border border-purple-500/20">
            <GitBranch className="w-6 h-6 text-purple-400" />
          </div>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative w-full md:w-80">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search execution, service, or explanation..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-950/60 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All Anomaly Types</option>
              <option value="LATENCY_SPIKE">Latency Spikes</option>
              <option value="UNUSUAL_PATH">Unusual DAG Paths</option>
              <option value="RETRY_STORM">Retry Storms</option>
              <option value="ERROR_CASCADE">Error Cascades</option>
              <option value="DEPENDENCY_TIMEOUT">Dependency Timeouts</option>
            </select>
          </div>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Severities</option>
            <option value="CRITICAL">Critical Only</option>
            <option value="WARNING">Warning Only</option>
            <option value="INFO">Info Only</option>
          </select>

          <button
            onClick={fetchAnomalies}
            className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm border border-slate-700 transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Anomalies Table */}
      <div className="bg-slate-900/60 rounded-xl border border-slate-800/80 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-950/70 border-b border-slate-800 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                <th className="py-3.5 px-4">Severity</th>
                <th className="py-3.5 px-4">Anomaly Type</th>
                <th className="py-3.5 px-4">Execution ID</th>
                <th className="py-3.5 px-4">Outlier Score</th>
                <th className="py-3.5 px-4">Impacted Services</th>
                <th className="py-3.5 px-4">Diagnostic Insight</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 text-sm">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    <Activity className="w-6 h-6 animate-spin mx-auto mb-2 text-cyan-500" />
                    Scanning telemetry and computing statistical baselines...
                  </td>
                </tr>
              ) : filteredAnomalies.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-500/80" />
                    No anomalies found matching current filters. System telemetry is within nominal thresholds.
                  </td>
                </tr>
              ) : (
                filteredAnomalies.map((anom) => (
                  <tr key={anom.id} className="hover:bg-slate-800/40 transition-colors group">
                    <td className="py-3.5 px-4 whitespace-nowrap">{getSeverityBadge(anom.severity)}</td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <div className="flex items-center gap-2 font-medium text-slate-200">
                        {getAnomalyTypeIcon(anom.anomaly_type)}
                        <span>{anom.anomaly_type.replace('_', ' ')}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap font-mono text-xs text-cyan-400">
                      {anom.execution_id.slice(0, 16)}...
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-slate-800 rounded-full h-2 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              anom.score >= 0.70 ? 'bg-rose-500' : anom.score >= 0.40 ? 'bg-amber-500' : 'bg-blue-500'
                            }`}
                            style={{ width: `${Math.min(100, Math.round(anom.score * 100))}%` }}
                          />
                        </div>
                        <span className="text-xs font-mono text-slate-300">{(anom.score * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex flex-wrap gap-1">
                        {anom.affected_services.map((svc) => (
                          <span
                            key={svc}
                            className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-slate-800 text-slate-300 border border-slate-700"
                          >
                            <Server className="w-2.5 h-2.5 mr-1 text-slate-500" />
                            {svc}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 max-w-md truncate text-slate-300" title={anom.explanation}>
                      {anom.explanation}
                    </td>
                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <button
                        onClick={() => setSelectedAnomaly(anom)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-cyan-950/60 hover:bg-cyan-900/80 text-cyan-400 border border-cyan-800/60 transition-all active:scale-95"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        Evidence
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Slide-Out Evidence Drawer */}
      {selectedAnomaly && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/80 backdrop-blur-sm flex justify-end animate-in fade-in duration-200">
          <div className="w-full max-w-xl bg-slate-900 border-l border-slate-800 h-full p-6 overflow-y-auto flex flex-col shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <h3 className="text-lg font-bold text-slate-100">Anomaly Diagnostic Evidence</h3>
              </div>
              <button
                onClick={() => setSelectedAnomaly(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="py-6 space-y-6 flex-1">
              {/* Header Info */}
              <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Classification</span>
                  {getSeverityBadge(selectedAnomaly.severity)}
                </div>
                <div className="flex items-center gap-2 text-lg font-bold text-slate-200">
                  {getAnomalyTypeIcon(selectedAnomaly.anomaly_type)}
                  {selectedAnomaly.anomaly_type.replace('_', ' ')}
                </div>
                <p className="text-sm text-slate-300 bg-slate-900/90 p-3 rounded-lg border border-slate-800">
                  {selectedAnomaly.explanation}
                </p>
              </div>

              {/* Execution & Affected Services */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-950/40 p-4 rounded-xl border border-slate-800">
                  <p className="text-xs text-slate-400 font-medium">Execution ID</p>
                  <p className="text-xs font-mono text-cyan-400 mt-1 break-all">{selectedAnomaly.execution_id}</p>
                </div>
                <div className="bg-slate-950/40 p-4 rounded-xl border border-slate-800">
                  <p className="text-xs text-slate-400 font-medium">Severity Score</p>
                  <p className="text-lg font-bold text-rose-400 mt-1">{(selectedAnomaly.score * 100).toFixed(1)}%</p>
                </div>
              </div>

              {/* Affected Services */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Impacted Services</h4>
                <div className="flex flex-wrap gap-2">
                  {selectedAnomaly.affected_services.map((svc) => (
                    <span
                      key={svc}
                      className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 text-slate-200 border border-slate-700 flex items-center gap-1.5"
                    >
                      <Server className="w-3 h-3 text-cyan-400" />
                      {svc}
                    </span>
                  ))}
                </div>
              </div>

              {/* Quantitative Supporting Evidence */}
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Zap className="w-3.5 h-3.5 text-amber-400" />
                  Statistical & Metric Evidence
                </h4>
                <div className="bg-slate-950/80 rounded-xl border border-slate-800 p-4 font-mono text-xs text-slate-300 space-y-2 overflow-x-auto">
                  <pre className="whitespace-pre-wrap">{JSON.stringify(selectedAnomaly.evidence, null, 2)}</pre>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setSelectedAnomaly(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium transition-colors"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
