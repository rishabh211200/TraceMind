import React from 'react';
import { Network, Terminal } from 'lucide-react';

interface HeaderProps {
  apiStatus: string;
}

export const Header: React.FC<HeaderProps> = ({ apiStatus }) => {
  return (
    <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <Network className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg tracking-tight text-slate-100">TraceMind</span>
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono border border-emerald-500/20">
                v0.1.0-alpha
              </span>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">AI-Powered Distributed Workflow Intelligence</p>
          </div>
        </div>

        {/* Status Indicators */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 text-xs font-mono px-3 py-1.5 rounded-md bg-slate-800/50 border border-slate-700/50">
            <div
              className={`h-2 w-2 rounded-full ${
                apiStatus === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span className="text-slate-300">API: {apiStatus}</span>
          </div>

          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center space-x-1.5 text-xs font-medium px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          >
            <Terminal className="h-3.5 w-3.5" />
            <span>OpenAPI Docs</span>
          </a>
        </div>
      </div>
    </header>
  );
};
