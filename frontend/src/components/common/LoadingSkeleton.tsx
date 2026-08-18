import React from 'react';

interface SkeletonProps {
  rows?: number;
  className?: string;
}

export const SkeletonCard: React.FC = () => (
  <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 animate-pulse">
    <div className="h-3.5 w-24 bg-slate-800 rounded mb-3" />
    <div className="h-7 w-32 bg-slate-700/60 rounded mb-2" />
    <div className="h-3 w-20 bg-slate-800/80 rounded" />
  </div>
);

export const SkeletonTable: React.FC<SkeletonProps> = ({ rows = 5, className = '' }) => (
  <div className={`bg-slate-900/50 border border-slate-800 rounded-xl p-4 animate-pulse ${className}`}>
    <div className="h-6 w-1/3 bg-slate-800 rounded mb-4" />
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, idx) => (
        <div key={idx} className="h-10 bg-slate-800/50 rounded flex items-center px-4 space-x-4">
          <div className="h-4 w-1/6 bg-slate-700/50 rounded" />
          <div className="h-4 w-1/4 bg-slate-700/50 rounded" />
          <div className="h-4 w-1/5 bg-slate-700/50 rounded" />
          <div className="h-4 w-1/6 bg-slate-700/50 rounded" />
        </div>
      ))}
    </div>
  </div>
);
