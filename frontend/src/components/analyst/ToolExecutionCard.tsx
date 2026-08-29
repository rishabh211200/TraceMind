import React, { useState } from 'react';
import { ToolCall, ToolResult } from '../../types/analyst';
import {
  ChevronDown,
  ChevronRight,
  Clock,
  Code2,
  Terminal,
  Wrench,
} from 'lucide-react';

interface ToolExecutionCardProps {
  toolCall: ToolCall;
  toolResult?: ToolResult;
}

export const ToolExecutionCard: React.FC<ToolExecutionCardProps> = ({
  toolCall,
  toolResult,
}) => {
  const [expanded, setExpanded] = useState<boolean>(false);

  return (
    <div className="my-2 bg-slate-950/80 border border-slate-800/90 rounded-xl overflow-hidden shadow-md text-xs">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full px-3.5 py-2 flex items-center justify-between bg-slate-900/60 hover:bg-slate-900/90 transition text-left"
      >
        <div className="flex items-center gap-2">
          <div className="p-1 rounded-md bg-indigo-950/80 border border-indigo-700/60 text-indigo-400">
            <Wrench className="w-3.5 h-3.5" />
          </div>
          <span className="font-mono font-semibold text-indigo-300">
            {toolCall.name}
          </span>
          {toolResult && (
            <span className="text-[10px] text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-2 py-0.5 rounded-full font-mono">
              Executed
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 text-slate-400">
          {toolResult && (
            <div className="flex items-center gap-1 font-mono text-[11px] text-slate-400">
              <Clock className="w-3 h-3 text-slate-400" />
              <span>{toolResult.execution_time_ms}ms</span>
            </div>
          )}
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="p-3.5 bg-slate-950 border-t border-slate-900 space-y-2.5 animate-fadeIn">
          {/* Tool Arguments */}
          <div>
            <div className="flex items-center gap-1 text-[11px] font-semibold text-slate-400 mb-1">
              <Terminal className="w-3 h-3 text-slate-400" />
              <span>Input Parameters</span>
            </div>
            <pre className="p-2 bg-slate-900/90 border border-slate-800/80 rounded-lg text-[11px] font-mono text-indigo-200 overflow-x-auto">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>

          {/* Tool Result Raw Evidence */}
          {toolResult && (
            <div>
              <div className="flex items-center gap-1 text-[11px] font-semibold text-slate-400 mb-1">
                <Code2 className="w-3 h-3 text-emerald-400" />
                <span>Raw Evidence Output</span>
              </div>
              <pre className="p-2 bg-slate-900/90 border border-slate-800/80 rounded-lg text-[11px] font-mono text-emerald-300 max-h-48 overflow-y-auto overflow-x-auto">
                {typeof toolResult.result === 'string'
                  ? toolResult.result
                  : JSON.stringify(toolResult.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
