import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error caught by ErrorBoundary:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[400px] flex flex-col items-center justify-center p-8 text-center">
          <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400 mb-4">
            <AlertTriangle className="h-10 w-10 mx-auto" />
          </div>
          <h2 className="text-lg font-bold text-slate-100 font-mono mb-2">
            Something went wrong rendering this view
          </h2>
          <p className="text-xs text-slate-400 font-mono max-w-md mb-6">
            {this.state.error?.message || 'An unexpected rendering error occurred.'}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-mono text-xs transition"
          >
            <RefreshCw className="h-4 w-4" />
            <span>Reload Dashboard</span>
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
