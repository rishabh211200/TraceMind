import React from 'react';
import {
  Network,
  Terminal,
  Activity,
  GitBranch,
  Layers,
  Server,
  Flame,
  Zap,
  AlertTriangle,
  SearchCheck,
} from 'lucide-react';

export type DashboardTab =
  | 'overview'
  | 'topology'
  | 'workflows'
  | 'executions'
  | 'anomalies'
  | 'root_cause'
  | 'services'
  | 'simulator';

interface HeaderProps {
  activeTab: DashboardTab;
  onSelectTab: (tab: DashboardTab) => void;
  apiStatus: string;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onSelectTab,
  apiStatus,
}) => {
  const tabs: { id: DashboardTab; label: string; icon: React.ElementType }[] = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'topology', label: 'Topology', icon: Network },
    { id: 'workflows', label: 'Workflows', icon: GitBranch },
    { id: 'executions', label: 'Traces', icon: Layers },
    { id: 'anomalies', label: 'Anomalies', icon: AlertTriangle },
    { id: 'root_cause', label: 'Root Cause', icon: SearchCheck },
    { id: 'services', label: 'Services', icon: Server },
    { id: 'simulator', label: 'Simulator', icon: Flame },
  ];

  return (
    <header className="border-b border-slate-800/80 bg-slate-900/80 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <div className="flex items-center space-x-3 shrink-0">
          <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <Zap className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-base tracking-tight text-slate-100 font-mono">TraceMind</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 font-mono border border-emerald-500/20">
                v0.4.0
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden xl:block font-mono">
              Distributed Workflow Intelligence
            </p>
          </div>
        </div>

        {/* View Navigation Tabs */}
        <nav className="flex items-center space-x-1 sm:space-x-1.5 overflow-x-auto py-1 px-2">
          {tabs.map(({ id, label, icon: Icon }) => {
            const isActive = activeTab === id;
            return (
              <button
                key={id}
                onClick={() => onSelectTab(id)}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono transition whitespace-nowrap ${
                  isActive
                    ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/40 font-semibold shadow-sm shadow-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <Icon className={`h-3.5 w-3.5 ${isActive ? 'text-emerald-400' : 'text-slate-400'}`} />
                <span>{label}</span>
              </button>
            );
          })}
        </nav>

        {/* Status Indicators & Docs Link */}
        <div className="flex items-center space-x-3 shrink-0">
          <div className="hidden sm:flex items-center space-x-2 text-[11px] font-mono px-2.5 py-1 rounded-md bg-slate-950/60 border border-slate-800">
            <span
              className={`h-2 w-2 rounded-full ${
                apiStatus === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span className="text-slate-300 capitalize">{apiStatus}</span>
          </div>

          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center space-x-1.5 text-xs font-mono px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          >
            <Terminal className="h-3.5 w-3.5 text-emerald-400" />
            <span className="hidden md:inline">OpenAPI</span>
          </a>
        </div>
      </div>
    </header>
  );
};
