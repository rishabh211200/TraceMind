import React from 'react';
import { ArrowRight, AlertCircle, AlertTriangle, ShieldAlert, Cpu } from 'lucide-react';

interface CausalGraphVisualizerProps {
  causalPath: string[];
  culpritService: string;
  incidentCategory: string;
  confidence: number;
}

export const CausalGraphVisualizer: React.FC<CausalGraphVisualizerProps> = ({
  causalPath,
  culpritService,
  incidentCategory,
  confidence,
}) => {
  if (!causalPath || causalPath.length === 0) {
    return (
      <div className="p-4 rounded-lg bg-gray-900/60 border border-gray-800 text-gray-400 text-sm flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-400" />
        <span>No causal propagation chain available for this diagnosis.</span>
      </div>
    );
  }

  return (
    <div className="p-5 rounded-xl bg-gray-900/80 border border-gray-800/80 backdrop-blur shadow-xl space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-red-400" />
          <h4 className="text-sm font-semibold text-gray-200 tracking-wide">
            Causal Propagation Chain
          </h4>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="px-2.5 py-0.5 rounded-full bg-red-950/60 border border-red-500/40 text-red-300 font-mono">
            {incidentCategory}
          </span>
          <span className="px-2.5 py-0.5 rounded-full bg-indigo-950/60 border border-indigo-500/40 text-indigo-300 font-mono">
            {(confidence * 100).toFixed(1)}% Confidence
          </span>
        </div>
      </div>

      {/* Horizontal Flow Chain */}
      <div className="flex items-center gap-2 overflow-x-auto py-3 px-1 scrollbar-thin scrollbar-thumb-gray-800">
        {causalPath.map((service, idx) => {
          const isRoot = idx === 0 || service === culpritService;
          const isTerminal = idx === causalPath.length - 1 && causalPath.length > 1;

          return (
            <React.Fragment key={`${service}-${idx}`}>
              <div
                className={`relative flex flex-col items-center min-w-[140px] max-w-[180px] p-3 rounded-lg border transition-all duration-200 ${
                  isRoot
                    ? 'bg-gradient-to-b from-red-950/70 to-red-900/30 border-red-500/80 shadow-[0_0_15px_rgba(239,68,68,0.2)]'
                    : isTerminal
                    ? 'bg-gradient-to-b from-rose-950/60 to-rose-900/20 border-rose-500/60 shadow-[0_0_10px_rgba(244,63,94,0.15)]'
                    : 'bg-gray-800/60 border-amber-500/50 shadow-sm'
                }`}
              >
                {/* Step indicator badge */}
                <div className="absolute -top-2.5 left-3 px-1.5 py-0.2 rounded text-[10px] font-mono font-bold tracking-wider uppercase">
                  {isRoot ? (
                    <span className="bg-red-600 text-white px-1.5 py-0.5 rounded shadow">
                      ROOT CAUSE
                    </span>
                  ) : isTerminal ? (
                    <span className="bg-rose-600 text-white px-1.5 py-0.5 rounded shadow">
                      SYMPTOM
                    </span>
                  ) : (
                    <span className="bg-amber-600 text-black font-semibold px-1.5 py-0.5 rounded shadow">
                      CASCADE {idx + 1}
                    </span>
                  )}
                </div>

                <div className="mt-1 flex items-center gap-1.5">
                  {isRoot ? (
                    <AlertCircle className="w-4 h-4 text-red-400 animate-pulse" />
                  ) : (
                    <Cpu className="w-4 h-4 text-gray-400" />
                  )}
                  <span
                    className={`text-xs font-semibold truncate ${
                      isRoot ? 'text-red-200 font-mono' : 'text-gray-200'
                    }`}
                  >
                    {service}
                  </span>
                </div>

                <span className="text-[11px] text-gray-400 mt-1">
                  {isRoot
                    ? 'Origin Point'
                    : isTerminal
                    ? 'Client Gateway'
                    : 'Degraded Dependency'}
                </span>
              </div>

              {idx < causalPath.length - 1 && (
                <div className="flex flex-col items-center px-1 text-gray-500">
                  <ArrowRight className="w-4 h-4 text-amber-400/80 animate-pulse" />
                  <span className="text-[9px] font-mono text-gray-500 mt-0.5">calls</span>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};
