import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { ApiError } from '../../types/api';

interface ErrorAlertProps {
  error: ApiError | Error | string | null;
  onRetry?: () => void;
  className?: string;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({ error, onRetry, className = '' }) => {
  if (!error) return null;

  let title = 'Error';
  let detail = '';

  if (typeof error === 'string') {
    detail = error;
  } else if ('detail' in error && error.detail) {
    title = (error as ApiError).title || 'API Error';
    detail = (error as ApiError).detail;
  } else if (error instanceof Error) {
    title = error.name;
    detail = error.message;
  }

  return (
    <div
      className={`p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-start justify-between space-x-3 ${className}`}
    >
      <div className="flex items-start space-x-3">
        <AlertTriangle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
        <div>
          <h4 className="text-sm font-semibold text-rose-200">{title}</h4>
          <p className="text-xs text-rose-300/90 mt-1 font-mono">{detail}</p>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center space-x-1.5 px-3 py-1 text-xs font-medium rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/40 transition shrink-0"
        >
          <RefreshCw className="h-3 w-3" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
};
