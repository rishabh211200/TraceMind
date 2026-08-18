import React, { useMemo } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  Node,
  Edge,
  MarkerType,
  Position,
  Handle,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { WorkflowDefinition, WorkflowNode } from '../../types/workflow';
import { GitCommit } from 'lucide-react';

interface WorkflowDagProps {
  workflow: WorkflowDefinition;
  onSelectNode?: (nodeId: string) => void;
  selectedNodeId?: string | null;
}

interface StepNodeData {
  step: WorkflowNode;
  isSelected: boolean;
  stepIndex: number;
}

const CustomWorkflowStepNode: React.FC<{ data: StepNodeData }> = ({ data }) => {
  const { step, isSelected, stepIndex } = data;

  const isSelectedStyle = isSelected
    ? 'border-emerald-400 ring-2 ring-emerald-400/30'
    : 'border-slate-700 hover:border-slate-500';

  return (
    <div
      className={`px-4 py-3 rounded-xl bg-slate-900/95 border backdrop-blur-md shadow-xl transition cursor-pointer min-w-[190px] ${isSelectedStyle}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-slate-500 !w-2 !h-2" />

      <div className="flex items-center space-x-2">
        <span className="h-5 w-5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-[10px] font-mono font-bold">
          {stepIndex + 1}
        </span>
        <div className="overflow-hidden">
          <p className="text-xs font-semibold text-slate-100 font-mono truncate">{step.id}</p>
          <p className="text-[11px] text-slate-400 font-mono truncate">{step.service}</p>
        </div>
      </div>

      {step.operation && (
        <div className="mt-2 pt-1.5 border-t border-slate-800/80 text-[10px] font-mono text-emerald-400/90 flex items-center space-x-1">
          <GitCommit className="h-3 w-3 shrink-0" />
          <span className="truncate">{step.operation}</span>
        </div>
      )}

      <Handle type="source" position={Position.Right} className="!bg-slate-500 !w-2 !h-2" />
    </div>
  );
};

const nodeTypes = {
  workflowStep: CustomWorkflowStepNode,
};

export const WorkflowDag: React.FC<WorkflowDagProps> = ({
  workflow,
  onSelectNode,
  selectedNodeId,
}) => {
  const { initialNodes, initialEdges } = useMemo(() => {
    // Topological linear layout spacing
    const nodes: Node[] = workflow.nodes.map((step, idx) => ({
      id: step.id,
      type: 'workflowStep',
      position: { x: idx * 230 + 40, y: 150 + (idx % 2 === 1 ? 40 : -40) },
      data: {
        step,
        isSelected: selectedNodeId === step.id,
        stepIndex: idx,
      },
    }));

    const edges: Edge[] = workflow.edges.map((e, idx) => ({
      id: `wf-edge-${idx}-${e.from}-${e.to}`,
      source: e.from,
      target: e.to,
      animated: true,
      label: e.condition || (e.weight && e.weight < 1.0 ? `w=${e.weight}` : undefined),
      style: { stroke: '#10b981', strokeWidth: 2 },
      labelStyle: { fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' },
      labelBgStyle: { fill: '#0f172a', fillOpacity: 0.9 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: '#10b981',
        width: 14,
        height: 14,
      },
    }));

    return { initialNodes: nodes, initialEdges: edges };
  }, [workflow, selectedNodeId]);

  return (
    <div className="w-full h-[360px] rounded-xl border border-slate-800 bg-slate-950 relative overflow-hidden">
      <ReactFlow
        nodes={initialNodes}
        edges={initialEdges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onSelectNode && onSelectNode(node.id)}
        fitView
        className="bg-slate-950"
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1.2} color="#334155" />
        <Controls className="!bg-slate-900 !border-slate-800 !text-slate-300" />
      </ReactFlow>
    </div>
  );
};
