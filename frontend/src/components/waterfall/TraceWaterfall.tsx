import React, { useState, useMemo } from 'react';
import { TraceTreeNode } from '../../types/execution';
import { SpanDetailDrawer } from './SpanDetailDrawer';
import {
  ChevronRight,
  ChevronDown,
  AlertCircle,
  Clock,
  RotateCcw,
  Layers,
} from 'lucide-react';

interface TraceWaterfallProps {
  rootNode: TraceTreeNode;
  totalDurationMs?: number;
}

interface FlattenedSpan {
  node: TraceTreeNode;
  depth: number;
  offsetMs: number;
  hasChildren: boolean;
}

export const TraceWaterfall: React.FC<TraceWaterfallProps> = ({
  rootNode,
  totalDurationMs: propTotalDuration,
}) => {
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());
  const [selectedSpan, setSelectedSpan] = useState<TraceTreeNode | null>(null);

  // Service color map for rich Gantt styling
  const serviceColors: Record<string, { bg: string; text: string; border: string }> = {
    'api-gateway': { bg: 'bg-sky-500', text: 'text-sky-400', border: 'border-sky-500/40' },
    'auth-service': { bg: 'bg-emerald-500', text: 'text-emerald-400', border: 'border-emerald-500/40' },
    'customer-service': { bg: 'bg-teal-500', text: 'text-teal-400', border: 'border-teal-500/40' },
    'customer-cache': { bg: 'bg-purple-500', text: 'text-purple-400', border: 'border-purple-500/40' },
    'customer-db': { bg: 'bg-amber-500', text: 'text-amber-400', border: 'border-amber-500/40' },
    'inventory-service': { bg: 'bg-cyan-500', text: 'text-cyan-400', border: 'border-cyan-500/40' },
    'inventory-db': { bg: 'bg-amber-600', text: 'text-amber-400', border: 'border-amber-500/40' },
    'pricing-service': { bg: 'bg-indigo-500', text: 'text-indigo-400', border: 'border-indigo-500/40' },
    'payment-service': { bg: 'bg-rose-500', text: 'text-rose-400', border: 'border-rose-500/40' },
    'payment-gateway': { bg: 'bg-red-500', text: 'text-red-400', border: 'border-red-500/40' },
    'order-service': { bg: 'bg-emerald-600', text: 'text-emerald-400', border: 'border-emerald-500/40' },
    'notification-service': { bg: 'bg-blue-500', text: 'text-blue-400', border: 'border-blue-500/40' },
  };

  const getServiceStyle = (svc: string) => {
    return (
      serviceColors[svc] || {
        bg: 'bg-slate-500',
        text: 'text-slate-300',
        border: 'border-slate-500/40',
      }
    );
  };

  // Compute root start time in epoch ms
  const rootStartTime = useMemo(() => {
    return new Date(rootNode.timestamp).getTime();
  }, [rootNode]);

  // Recursively flatten tree with depth & relative offset
  const { flattenedSpans, totalDurationMs } = useMemo(() => {
    const list: FlattenedSpan[] = [];
    let maxEndTime = rootStartTime + (rootNode.latency_ms || 1.0);

    const traverse = (node: TraceTreeNode, depth: number) => {
      const nodeTime = new Date(node.timestamp).getTime();
      const offsetMs = Math.max(0, nodeTime - rootStartTime);
      const spanEnd = nodeTime + (node.latency_ms || 0.0);
      if (spanEnd > maxEndTime) {
        maxEndTime = spanEnd;
      }

      const hasChildren = node.children && node.children.length > 0;
      list.push({
        node,
        depth,
        offsetMs,
        hasChildren,
      });

      if (hasChildren && !collapsedIds.has(node.event_id)) {
        for (const child of node.children) {
          traverse(child, depth + 1);
        }
      }
    };

    traverse(rootNode, 0);
    const calculatedDuration = propTotalDuration || Math.max(maxEndTime - rootStartTime, rootNode.latency_ms || 1.0, 1.0);

    return { flattenedSpans: list, totalDurationMs: calculatedDuration };
  }, [rootNode, collapsedIds, rootStartTime, propTotalDuration]);

  const toggleCollapse = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Timeline ticks (0%, 25%, 50%, 75%, 100%)
  const ticks = [0, 0.25, 0.5, 0.75, 1.0];

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden shadow-2xl relative">
      {/* Header Bar */}
      <div className="px-5 py-3 border-b border-slate-800/80 bg-slate-900/60 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <Layers className="h-4 w-4 text-emerald-400" />
          <span className="text-xs font-semibold text-slate-100 font-mono">
            Distributed Trace Waterfall
          </span>
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
            {flattenedSpans.length} spans
          </span>
        </div>
        <div className="flex items-center space-x-2 text-xs font-mono text-slate-400">
          <Clock className="h-3.5 w-3.5" />
          <span>Total: <strong className="text-slate-200">{totalDurationMs.toFixed(2)}ms</strong></span>
        </div>
      </div>

      {/* Waterfall Grid Container */}
      <div className="overflow-x-auto">
        <div className="min-w-[850px]">
          {/* Timeline Axis Header */}
          <div className="grid grid-cols-12 border-b border-slate-800 bg-slate-900/40 text-[10px] font-mono text-slate-400 py-2 px-4">
            <div className="col-span-5 uppercase tracking-wider font-semibold">
              Span / Operation
            </div>
            <div className="col-span-7 relative">
              <div className="flex justify-between w-full pr-4">
                {ticks.map((ratio) => (
                  <span key={ratio} className="select-none">
                    {(totalDurationMs * ratio).toFixed(1)}ms
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Spans List */}
          <div className="divide-y divide-slate-900">
            {flattenedSpans.map(({ node, depth, offsetMs, hasChildren }) => {
              const style = getServiceStyle(node.service);
              const leftPercent = Math.min(Math.max((offsetMs / totalDurationMs) * 100, 0), 99);
              const widthPercent = Math.min(
                Math.max((node.latency_ms / totalDurationMs) * 100, 1.0),
                100 - leftPercent
              );

              const isFailed = node.status === 'FAILED' || node.event_type === 'SPAN_ERROR';
              const isTimeout = node.status === 'TIMEOUT' || node.event_type === 'SPAN_TIMEOUT';
              const isRetry = node.event_type === 'RETRY_ATTEMPT';

              return (
                <div
                  key={node.event_id}
                  onClick={() => setSelectedSpan(node)}
                  className={`grid grid-cols-12 items-center px-4 py-2 hover:bg-slate-900/80 cursor-pointer transition text-xs font-mono ${
                    selectedSpan?.event_id === node.event_id ? 'bg-slate-900 ring-1 ring-emerald-500/30' : ''
                  }`}
                >
                  {/* Operation & Service Column */}
                  <div
                    className="col-span-5 flex items-center space-x-1.5 overflow-hidden pr-3"
                    style={{ paddingLeft: `${depth * 18}px` }}
                  >
                    {hasChildren ? (
                      <button
                        onClick={(e) => toggleCollapse(node.event_id, e)}
                        className="p-0.5 hover:bg-slate-800 rounded text-slate-400 hover:text-slate-200 transition"
                      >
                        {collapsedIds.has(node.event_id) ? (
                          <ChevronRight className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5" />
                        )}
                      </button>
                    ) : (
                      <span className="w-4" />
                    )}

                    {isFailed ? (
                      <AlertCircle className="h-3.5 w-3.5 text-rose-400 shrink-0" />
                    ) : isTimeout ? (
                      <Clock className="h-3.5 w-3.5 text-amber-400 shrink-0" />
                    ) : isRetry ? (
                      <RotateCcw className="h-3.5 w-3.5 text-purple-400 shrink-0" />
                    ) : (
                      <span className="h-2 w-2 rounded-full bg-emerald-400 shrink-0" />
                    )}

                    <span className="font-semibold text-slate-200 truncate">{node.operation}</span>
                    <span className={`text-[10px] px-1.5 py-0.2 rounded border truncate ${style.border} ${style.text}`}>
                      {node.service}
                    </span>
                  </div>

                  {/* Gantt Bar Column */}
                  <div className="col-span-7 relative h-7 flex items-center pr-4">
                    {/* Background Grid Lines */}
                    <div className="absolute inset-0 flex justify-between pointer-events-none opacity-10">
                      {ticks.map((ratio) => (
                        <div key={ratio} className="w-px h-full bg-slate-400" />
                      ))}
                    </div>

                    {/* Span Bar */}
                    <div
                      className="absolute h-4 rounded-md transition-all flex items-center px-1.5 shadow-sm shadow-black/40 group overflow-hidden"
                      style={{
                        left: `${leftPercent}%`,
                        width: `${widthPercent}%`,
                        backgroundColor: isFailed ? '#f43f5e' : isTimeout ? '#f59e0b' : undefined,
                      }}
                    >
                      <div
                        className={`w-full h-full rounded-md ${
                          !isFailed && !isTimeout ? style.bg : ''
                        } opacity-90`}
                      />
                      <span className="absolute right-1 text-[9px] font-bold text-white/90 drop-shadow select-none whitespace-nowrap">
                        {node.latency_ms.toFixed(1)}ms
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Span Details Drawer */}
      <SpanDetailDrawer span={selectedSpan} onClose={() => setSelectedSpan(null)} />
    </div>
  );
};
