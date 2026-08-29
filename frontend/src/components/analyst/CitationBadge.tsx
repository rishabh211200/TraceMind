import React, { useState } from 'react';
import { Citation } from '../../types/analyst';
import { CheckCircle, ShieldCheck } from 'lucide-react';

interface CitationBadgeProps {
  citation: Citation;
}

export const CitationBadge: React.FC<CitationBadgeProps> = ({ citation }) => {
  const [showTooltip, setShowTooltip] = useState<boolean>(false);

  return (
    <span className="relative inline-block ml-1 align-baseline">
      <button
        type="button"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onClick={() => setShowTooltip(!showTooltip)}
        className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-mono font-bold bg-indigo-950/80 hover:bg-indigo-900/90 text-indigo-300 border border-indigo-700/60 rounded-md transition cursor-pointer shadow-sm"
        title={`Evidence: ${citation.tool_name}`}
      >
        <ShieldCheck className="w-2.5 h-2.5 text-indigo-400" />
        [{citation.citation_id}]
      </button>

      {showTooltip && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 bg-slate-900 border border-indigo-600/80 rounded-xl shadow-2xl text-left pointer-events-none animate-fadeIn">
          <div className="flex items-center gap-1.5 text-[11px] font-bold text-indigo-300 border-b border-slate-800 pb-1 mb-1.5">
            <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
            <span>Verified Tool Evidence #{citation.citation_id}</span>
          </div>
          <div className="space-y-1 text-[10px] text-slate-300">
            <div>
              <span className="text-slate-400">Tool:</span>{' '}
              <span className="font-mono text-indigo-200">{citation.tool_name}</span>
            </div>
            <div>
              <span className="text-slate-400">Field:</span>{' '}
              <span className="font-mono text-slate-200">{citation.field_name}</span>
            </div>
            <div>
              <span className="text-slate-400">Value:</span>{' '}
              <span className="font-mono text-emerald-300 font-semibold">{String(citation.verified_value)}</span>
            </div>
            {citation.snippet && (
              <div className="pt-1 text-[9px] text-slate-400 italic border-t border-slate-800/80 mt-1">
                "{citation.snippet}"
              </div>
            )}
          </div>
        </div>
      )}
    </span>
  );
};
