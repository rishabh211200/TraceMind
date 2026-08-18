import React from 'react';
import { TraceTreeNode } from '../../types/execution';
import { X, Clock, Layers } from 'lucide-react';
import { Badge } from '../common/Badge';

interface SpanDetailDrawerProps {
  span: TraceTreeNode | null;
  onClose: () => void;
}

export const SpanDetailDrawer: React.FC<SpanDetailDrawerProps> = ({ span, onClose }) => {
  if (!span) return null;

  const isFailed = span.status === 'FAILED' || span.event_type === 'SPAN_ERROR';
  const isTimeout = span.status === 'TIMEOUT' || span.event_type === 'SPAN_TIMEOUT';

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-slate-900/95 border-l border-slate-800 shadow-2xl backdrop-blur-md z-50 flex flex-col transition-all">
      {/* Drawer Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Layers className="h-4 w-4 text-emerald-400" />
          <h3 className="text-sm font-semibold text-slate-100 font-mono">Span Inspector</h3>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Drawer Content */}
      <div className="p-5 overflow-y-auto space-y-5 flex-1 text-xs font-mono">
        {/* Status Banner */}
        <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950/70 border border-slate-800">
          <span className="text-slate-400">Status</span>
          <Badge
            variant={isFailed ? 'danger' : isTimeout ? 'warning' : 'success'}
            size="md"
          >
            {span.status}
          </Badge>
        </div>

        {/* Core Attributes */}
        <div className="space-y-3">
          <div>
            <label className="text-slate-500 uppercase tracking-wider text-[10px]">Operation</label>
            <p className="text-slate-100 font-semibold mt-0.5 text-sm">{span.operation}</p>
          </div>
          <div>
            <label className="text-slate-500 uppercase tracking-wider text-[10px]">Service</label>
            <p className="text-emerald-400 mt-0.5">{span.service}</p>
          </div>
          <div>
            <label className="text-slate-500 uppercase tracking-wider text-[10px]">Duration / Latency</label>
            <div className="flex items-center space-x-2 mt-0.5">
              <Clock className="h-3.5 w-3.5 text-slate-400" />
              <span className="text-slate-100 font-bold">{span.latency_ms.toFixed(2)} ms</span>
            </div>
          </div>
          <div>
            <label className="text-slate-500 uppercase tracking-wider text-[10px]">Event Type</label>
            <p className="text-slate-300 mt-0.5">{span.event_type}</p>
          </div>
          <div>
            <label className="text-slate-500 uppercase tracking-wider text-[10px]">Timestamp (UTC)</label>
            <p className="text-slate-400 mt-0.5">{new Date(span.timestamp).toISOString()}</p>
          </div>
        </div>

        {/* Trace Identifiers */}
        <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 space-y-2 text-[11px]">
          <div>
            <span className="text-slate-500 block text-[10px]">EVENT ID</span>
            <span className="text-slate-300 select-all">{span.event_id}</span>
          </div>
          {span.parent_event_id && (
            <div>
              <span className="text-slate-500 block text-[10px]">PARENT EVENT ID</span>
              <span className="text-slate-400 select-all">{span.parent_event_id}</span>
            </div>
          )}
          {span.correlation_id && (
            <div>
              <span className="text-slate-500 block text-[10px]">CORRELATION ID</span>
              <span className="text-slate-400 select-all">{span.correlation_id}</span>
            </div>
          )}
        </div>

        {/* Metadata */}
        {span.metadata && Object.keys(span.metadata).length > 0 && (
          <div>
            <label className="text-slate-500 uppercase tracking-wider text-[10px] block mb-1.5">
              Span Metadata
            </label>
            <pre className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300 overflow-x-auto">
              {JSON.stringify(span.metadata, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};
