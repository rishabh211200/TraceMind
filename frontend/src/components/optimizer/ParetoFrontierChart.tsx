import React from 'react';
import { ParetoPoint } from '../../types/optimizer';
import { Sparkles, CheckCircle2 } from 'lucide-react';

interface ParetoFrontierChartProps {
  points: ParetoPoint[];
  selectedPathId?: string;
  recommendedPathId?: string;
  onSelectPath?: (pathId: string) => void;
}

export const ParetoFrontierChart: React.FC<ParetoFrontierChartProps> = ({
  points,
  selectedPathId,
  recommendedPathId,
  onSelectPath,
}) => {
  if (!points || points.length === 0) {
    return (
      <div className="p-8 text-center text-slate-400 bg-slate-900/50 rounded-xl border border-slate-800">
        No candidate paths available for Pareto frontier visualization.
      </div>
    );
  }

  // Find min and max for scaling
  const minLat = Math.min(...points.map((p) => p.observed_latency_ms));
  const maxLat = Math.max(...points.map((p) => p.observed_latency_ms));
  const latPadding = Math.max(30, (maxLat - minLat) * 0.15);
  const xMin = Math.max(0, minLat - latPadding);
  const xMax = maxLat + latPadding;

  const minCost = Math.min(...points.map((p) => p.modeled_cost_units));
  const maxCost = Math.max(...points.map((p) => p.modeled_cost_units));
  const costPadding = Math.max(2, (maxCost - minCost) * 0.2);
  const yMin = Math.max(0, minCost - costPadding);
  const yMax = maxCost + costPadding;

  const width = 580;
  const height = 280;
  const padLeft = 60;
  const padRight = 30;
  const padTop = 30;
  const padBottom = 45;

  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;

  const getX = (lat: number) => {
    return padLeft + ((lat - xMin) / (xMax - xMin || 1)) * plotWidth;
  };

  const getY = (cost: number) => {
    // Y inverted: lower cost at the bottom, higher cost at the top
    return height - padBottom - ((cost - yMin) / (yMax - yMin || 1)) * plotHeight;
  };

  // Sort Pareto optimal points by latency to draw frontier line
  const paretoPoints = points
    .filter((p) => p.is_pareto_optimal)
    .sort((a, b) => a.observed_latency_ms - b.observed_latency_ms);

  const frontierPathD = paretoPoints
    .map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${getX(p.observed_latency_ms)} ${getY(p.modeled_cost_units)}`)
    .join(' ');

  return (
    <div className="bg-slate-900/90 backdrop-blur border border-slate-800/80 rounded-xl p-5 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-emerald-400" />
            3D Multi-Objective Pareto Frontier
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Non-dominated trade-off frontier between Observed Latency, Modeled Cost, and Reliability.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1.5 text-emerald-400">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 ring-emerald-500/30" />
            Pareto Optimal
          </span>
          <span className="flex items-center gap-1.5 text-slate-400">
            <span className="w-2.5 h-2.5 rounded-full bg-slate-600" />
            Dominated Path
          </span>
        </div>
      </div>

      <div className="relative flex justify-center">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full max-w-2xl overflow-visible">
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
            const y = padTop + pct * plotHeight;
            const costVal = yMax - pct * (yMax - yMin);
            return (
              <g key={`h-grid-${i}`}>
                <line
                  x1={padLeft}
                  y1={y}
                  x2={width - padRight}
                  y2={y}
                  stroke="#334155"
                  strokeDasharray="3 3"
                  strokeOpacity="0.4"
                />
                <text
                  x={padLeft - 10}
                  y={y + 4}
                  textAnchor="end"
                  className="fill-slate-400 text-[10px] font-mono"
                >
                  {costVal.toFixed(1)}u
                </text>
              </g>
            );
          })}

          {[0, 0.33, 0.66, 1].map((pct, i) => {
            const x = padLeft + pct * plotWidth;
            const latVal = xMin + pct * (xMax - xMin);
            return (
              <g key={`v-grid-${i}`}>
                <line
                  x1={x}
                  y1={padTop}
                  x2={x}
                  y2={height - padBottom}
                  stroke="#334155"
                  strokeDasharray="3 3"
                  strokeOpacity="0.4"
                />
                <text
                  x={x}
                  y={height - padBottom + 16}
                  textAnchor="middle"
                  className="fill-slate-400 text-[10px] font-mono"
                >
                  {Math.round(latVal)}ms
                </text>
              </g>
            );
          })}

          {/* Axes */}
          <line
            x1={padLeft}
            y1={height - padBottom}
            x2={width - padRight}
            y2={height - padBottom}
            stroke="#475569"
            strokeWidth="1.5"
          />
          <line
            x1={padLeft}
            y1={padTop}
            x2={padLeft}
            y2={height - padBottom}
            stroke="#475569"
            strokeWidth="1.5"
          />

          {/* Axis Labels */}
          <text
            x={padLeft + plotWidth / 2}
            y={height - 8}
            textAnchor="middle"
            className="fill-slate-300 text-[11px] font-medium tracking-wide"
          >
            Observed Latency (ms) — Lower is Better →
          </text>
          <text
            transform={`rotate(-90 ${16} ${padTop + plotHeight / 2})`}
            x={16}
            y={padTop + plotHeight / 2}
            textAnchor="middle"
            className="fill-slate-300 text-[11px] font-medium tracking-wide"
          >
            Modeled Cost Units (u)
          </text>

          {/* Pareto Frontier Line */}
          {frontierPathD && (
            <path
              d={frontierPathD}
              fill="none"
              stroke="#10b981"
              strokeWidth="2.5"
              strokeDasharray="5 4"
              className="drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]"
            />
          )}

          {/* Scatter Points */}
          {points.map((p) => {
            const cx = getX(p.observed_latency_ms);
            const cy = getY(p.modeled_cost_units);
            const isRec = p.path_id === recommendedPathId;
            const isSelected = p.path_id === selectedPathId;
            const isPareto = p.is_pareto_optimal;

            return (
              <g
                key={p.path_id}
                className="cursor-pointer transition-transform duration-150 hover:scale-125"
                onClick={() => onSelectPath && onSelectPath(p.path_id)}
              >
                {/* Highlight ring for recommended / selected */}
                {(isRec || isSelected) && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r="14"
                    fill="none"
                    stroke={isRec ? '#10b981' : '#38bdf8'}
                    strokeWidth="2"
                    className="animate-pulse"
                  />
                )}

                {/* Point Body */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={isRec ? 8 : isPareto ? 6.5 : 5}
                  fill={
                    isRec
                      ? '#10b981'
                      : isPareto
                      ? '#059669'
                      : '#64748b'
                  }
                  stroke="#0f172a"
                  strokeWidth="2"
                />

                {/* Path label badge */}
                <text
                  x={cx}
                  y={cy - 12}
                  textAnchor="middle"
                  className={`text-[10px] font-mono font-bold ${
                    isRec
                      ? 'fill-emerald-300 font-extrabold'
                      : isPareto
                      ? 'fill-emerald-400'
                      : 'fill-slate-400'
                  }`}
                >
                  {p.path_id}
                  {isRec ? ' ★' : ''}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Legend & Summary Footer */}
      <div className="mt-4 pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between text-xs text-slate-400">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            Pareto paths are mathematically non-dominated across all 3 criteria.
          </span>
        </div>
        <div>
          Click any point to inspect detailed step-by-step metrics & cost breakdown.
        </div>
      </div>
    </div>
  );
};
