import React, { useEffect, useState } from 'react';
import { DashboardTab, Header } from './components/Header';
import { OverviewView } from './views/OverviewView';
import { TopologyView } from './views/TopologyView';
import { WorkflowsView } from './views/WorkflowsView';
import { ExecutionsView } from './views/ExecutionsView';
import { ServicesView } from './views/ServicesView';
import { SimulatorView } from './views/SimulatorView';
import { AnomaliesView } from './views/AnomaliesView';
import { RootCauseView } from './views/RootCauseView';
import { OptimizerView } from './views/OptimizerView';
import { AnalystView } from './views/AnalystView';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<DashboardTab>('overview');
  const [apiHealth, setApiHealth] = useState<string>('checking...');

  // Navigation Context Parameters
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/v1/health')
      .then((res) => {
        if (!res.ok) throw new Error('API unreachable');
        return res.json();
      })
      .then((data) => {
        setApiHealth(data.status || 'healthy');
      })
      .catch(() => {
        setApiHealth('standby');
      });
  }, []);

  const handleNavigate = (tab: string, context?: Record<string, unknown>) => {
    if (context?.serviceName) {
      setSelectedService(String(context.serviceName));
    }
    if (context?.workflowId) {
      setSelectedWorkflowId(String(context.workflowId));
    }
    if (context?.executionId) {
      setSelectedExecutionId(String(context.executionId));
    }
    setActiveTab(tab as DashboardTab);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-emerald-500/30 selection:text-emerald-200">
      {/* Top Header Navigation */}
      <Header activeTab={activeTab} onSelectTab={setActiveTab} apiStatus={apiHealth} />

      {/* Main View Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'overview' && (
          <OverviewView onNavigateTab={handleNavigate} />
        )}

        {activeTab === 'topology' && (
          <TopologyView initialServiceName={selectedService} />
        )}

        {activeTab === 'workflows' && (
          <WorkflowsView
            initialWorkflowId={selectedWorkflowId}
            onNavigateExecution={(id) => handleNavigate('executions', { executionId: id })}
          />
        )}

        {activeTab === 'executions' && (
          <ExecutionsView initialExecutionId={selectedExecutionId} />
        )}

        {activeTab === 'anomalies' && (
          <AnomaliesView />
        )}

        {activeTab === 'root_cause' && (
          <RootCauseView />
        )}

        {activeTab === 'optimizer' && (
          <OptimizerView />
        )}

        {activeTab === 'analyst' && (
          <AnalystView />
        )}

        {activeTab === 'services' && (
          <ServicesView initialServiceName={selectedService} />
        )}

        {activeTab === 'simulator' && (
          <SimulatorView onNavigateExecutions={() => setActiveTab('executions')} />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 py-4 text-center text-xs font-mono text-slate-500">
        TraceMind &bull; AI-Powered Distributed Workflow Intelligence Platform &bull; Milestone 10
      </footer>
    </div>
  );
};
