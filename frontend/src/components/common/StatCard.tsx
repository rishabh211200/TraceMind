import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  iconColor?: string;
  badge?: string;
  badgeType?: 'success' | 'warning' | 'danger' | 'info';
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  iconColor = 'text-emerald-400',
  badge,
  badgeType = 'info',
}) => {
  const badgeStyles = {
    success: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    warning: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    danger: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    info: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  };

  return (
    <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl p-5 backdrop-blur-sm relative overflow-hidden transition hover:border-slate-700/80 shadow-lg shadow-black/20">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">{title}</p>
          <p className="text-2xl font-bold text-slate-100 mt-2 font-mono tracking-tight">{value}</p>
          {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
        </div>
        <div className="flex flex-col items-end space-y-2">
          <div className={`p-2.5 rounded-lg bg-slate-800/70 border border-slate-700/60 ${iconColor}`}>
            <Icon className="h-5 w-5" />
          </div>
          {badge && (
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-mono border ${badgeStyles[badgeType]}`}
            >
              {badge}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
