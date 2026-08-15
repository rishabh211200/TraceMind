import React, { useEffect, useState } from 'react';
import { Header } from './components/Header';
import {
  Activity,
  Cpu,
  Database,
  Network,
  Zap,
  BarChart3,
  Bot,
  AlertTriangle,
  GitBranch,
  Layers,
  Sparkles,
  CheckCircle2,
} from 'lucide-react';

interface ModuleStatus {
  name: string;
  code: string;
  description: string;
  status: 'active' | 'ready' | 'planned';
  icon: React.ElementType;
}

export const App: React.FC = () => {
  const [apiHealth, setApiHealth] = useState<string>('checking...');
  const [environment, setEnvironment] = useState<string>('development');

  useEffect(() => {
    fetch('/api/v1/health')
      .then((res) => {
        if (!res.ok) throw new Error('API unreachable');
        return res.json();
      })
      .then((data) => {
        setApiHealth(data.status || 'healthy');
        setEnvironment(data.environment || 'development');
      })
      .catch(() => {
        setApiHealth('standby (local dev)');
      });
  }, []);

  const modules: ModuleStatus[] = [
    {
      code: 'Module A',
      name: 'TraceSim Engine',
      description: 'Deterministic discrete-event simulator generating multi-service workflow execution traces with synthetic chaos.',
      status: 'ready',
      icon: Zap,
    },
    {
      code: 'Module B',
      name: 'Trace Store',
      description: 'High-performance time-series storage and indexing for trace spans, executions, and service dependencies.',
      status: 'ready',
      icon: Database,
    },
    {
      code: 'Module C',
      name: 'Workflow Intelligence',
      description: 'Graph mining and transition topology construction across distributed execution paths.',
      status: 'ready',
      icon: GitBranch,
    },
    {
      code: 'Module D',
      name: 'ML Failure & Latency Engine',
      description: 'Supervised classification and regression models predicting workflow outcomes with SHAP explainability.',
      status: 'ready',
      icon: Cpu,
    },
    {
      code: 'Module E',
      name: 'Root Cause Reasoner',
      description: 'Deterministic causal graph reasoning pinpointing root degradation sources before AI synthesis.',
      status: 'ready',
      icon: AlertTriangle,
    },
    {
      code: 'Module F',
      name: 'Workflow Optimizer',
      description: 'Multi-objective routing and path optimization balancing latency, reliability, and cost.',
      status: 'ready',
      icon: BarChart3,
    },
    {
      code: 'Module G',
      name: 'AI Analyst',
      description: 'Safe, tool-grounded conversational intelligence delivering factual, hallucination-free technical explanations.',
      status: 'ready',
      icon: Bot,
    },
    {
      code: 'Module H',
      name: 'Interactive Dashboard',
      description: 'Developer workspace with React Flow topological maps and trace waterfall Gantt visualizers.',
      status: 'active',
      icon: Layers,
    },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Header apiStatus={apiHealth} />

      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
        {/* Hero / Architecture Banner */}
        <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-b from-slate-900/90 to-slate-950/80 p-8 mb-8 backdrop-blur-sm shadow-2xl">
          <div className="absolute top-0 right-0 -mt-8 -mr-8 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />

          <div className="relative z-10 max-w-3xl">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono mb-4">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Milestone 0: Foundation Initialized</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mb-3">
              TraceMind Workflow Intelligence
            </h1>
            <p className="text-slate-300 text-sm sm:text-base leading-relaxed mb-6">
              An experimental AI system that learns behavioral patterns from distributed-system workflow execution traces.
              Predicting in-flight failures, pinpointing root causes with graph reasoning, and optimizing execution strategies using synthetic, reproducible datasets.
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 border-t border-slate-800/80">
              <div>
                <span className="text-xs text-slate-400 font-mono block">ENVIRONMENT</span>
                <span className="text-sm font-semibold text-slate-200 uppercase">{environment}</span>
              </div>
              <div>
                <span className="text-xs text-slate-400 font-mono block">SIMULATOR</span>
                <span className="text-sm font-semibold text-emerald-400">Deterministic</span>
              </div>
              <div>
                <span className="text-xs text-slate-400 font-mono block">ML ENGINE</span>
                <span className="text-sm font-semibold text-slate-200">XGBoost / SHAP</span>
              </div>
              <div>
                <span className="text-xs text-slate-400 font-mono block">AI AGENT</span>
                <span className="text-sm font-semibold text-slate-200">Tool-Grounded</span>
              </div>
            </div>
          </div>
        </div>

        {/* Modules Grid */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-200 flex items-center space-x-2">
              <Activity className="h-4 w-4 text-emerald-400" />
              <span>Core Architecture Modules</span>
            </h2>
            <span className="text-xs font-mono text-slate-400">8 Modules Registered</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {modules.map((mod) => {
              const Icon = mod.icon;
              return (
                <div
                  key={mod.code}
                  className="rounded-xl border border-slate-800/80 bg-slate-900/50 hover:bg-slate-900/80 p-5 transition duration-200 flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                        {mod.code}
                      </span>
                      <div className="flex items-center space-x-1">
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                        <span className="text-xs text-emerald-400 capitalize">{mod.status}</span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2.5 mb-2">
                      <div className="p-2 rounded-lg bg-slate-800/80 text-emerald-400 border border-slate-700/60">
                        <Icon className="h-4 w-4" />
                      </div>
                      <h3 className="font-semibold text-sm text-slate-100">{mod.name}</h3>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">{mod.description}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Standard Workflow Services simulated */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
          <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center space-x-2">
            <Network className="h-4 w-4 text-slate-400" />
            <span>Simulated Generic Distributed Services</span>
          </h3>
          <div className="flex flex-wrap gap-2">
            {[
              'auth-service',
              'customer-service',
              'inventory-service',
              'pricing-service',
              'payment-service',
              'order-service',
              'notification-service',
            ].map((svc) => (
              <span
                key={svc}
                className="px-3 py-1 rounded-md text-xs font-mono bg-slate-800/80 text-slate-300 border border-slate-700"
              >
                {svc}
              </span>
            ))}
          </div>
        </div>
      </main>

      <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500 font-mono">
        TraceMind v0.1.0 • Open Source AI Workflow Intelligence • Milestone 0 Initialized
      </footer>
    </div>
  );
};
