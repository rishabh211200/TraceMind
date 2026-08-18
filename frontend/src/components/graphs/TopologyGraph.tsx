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
import { ServiceTopology, TopologyNode } from '../../types/service';
import { Server, Database, Zap, Cpu, Network } from 'lucide-react';

interface TopologyGraphProps {
  topology: ServiceTopology;
  onSelectService?: (serviceName: string) => void;
  selectedServiceName?: string | null;
}

// Custom Service Node Component for React Flow
interface CustomNodeData {
  node: TopologyNode;
  isSelected: boolean;
}

const CustomServiceNode: React.FC<{ data: CustomNodeData }> = ({ data }) => {
  const { node, isSelected } = data;

  const isInfra = node.type.startsWith('infrastructure_') || node.type === 'api_gateway';

  const getIcon = () => {
    if (node.type === 'infrastructure_database') return <Database className="h-4 w-4 text-amber-400" />;
    if (node.type === 'infrastructure_cache') return <Zap className="h-4 w-4 text-purple-400" />;
    if (node.type === 'api_gateway') return <Network className="h-4 w-4 text-sky-400" />;
    if (node.name.includes('pricing') || node.name.includes('auth')) return <Cpu className="h-4 w-4 text-emerald-400" />;
    return <Server className="h-4 w-4 text-emerald-400" />;
  };

  const getBorderColor = () => {
    if (isSelected) return 'border-emerald-400 ring-2 ring-emerald-400/30 shadow-emerald-500/20';
    if (node.type === 'infrastructure_database') return 'border-amber-500/40 hover:border-amber-400';
    if (node.type === 'infrastructure_cache') return 'border-purple-500/40 hover:border-purple-400';
    if (node.type === 'api_gateway') return 'border-sky-500/40 hover:border-sky-400';
    return 'border-slate-700 hover:border-emerald-500/60';
  };

  const getBadgeStyle = () => {
    if (node.type === 'infrastructure_database') return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    if (node.type === 'infrastructure_cache') return 'bg-purple-500/10 text-purple-400 border-purple-500/30';
    if (node.type === 'api_gateway') return 'bg-sky-500/10 text-sky-400 border-sky-500/30';
    return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
  };

  return (
    <div
      className={`px-4 py-3 rounded-xl bg-slate-900/95 border backdrop-blur-md shadow-xl transition-all cursor-pointer min-w-[200px] ${getBorderColor()}`}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-500 !w-2 !h-2" />
      <Handle type="target" position={Position.Left} className="!bg-slate-500 !w-2 !h-2" id="left" />

      <div className="flex items-center space-x-2.5">
        <div className="p-1.5 rounded-lg bg-slate-800 border border-slate-700">{getIcon()}</div>
        <div className="overflow-hidden">
          <p className="text-xs font-semibold text-slate-100 font-mono truncate">{node.name}</p>
          <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono border ${getBadgeStyle()}`}>
            {isInfra ? node.type.replace('infrastructure_', '') : 'service'}
          </span>
        </div>
      </div>

      <div className="mt-2.5 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
        <span>Cap: <strong className="text-slate-200">{node.capacity}</strong></span>
        <span>Base: <strong className="text-slate-200">{node.baseline_latency_ms}ms</strong></span>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-slate-500 !w-2 !h-2" />
      <Handle type="source" position={Position.Right} className="!bg-slate-500 !w-2 !h-2" id="right" />
    </div>
  );
};

const nodeTypes = {
  serviceNode: CustomServiceNode,
};

export const TopologyGraph: React.FC<TopologyGraphProps> = ({
  topology,
  onSelectService,
  selectedServiceName,
}) => {
  // Compute hierarchical layout coordinates for services & infra dependencies
  const { initialNodes, initialEdges } = useMemo(() => {
    // Spatial layout positions for the 12 microservices/infrastructure nodes
    const positions: Record<string, { x: number; y: number }> = {
      'api-gateway': { x: 380, y: 30 },
      'auth-service': { x: 380, y: 150 },
      'customer-service': { x: 180, y: 280 },
      'customer-cache': { x: 20, y: 240 },
      'customer-db': { x: 20, y: 340 },
      'inventory-service': { x: 420, y: 280 },
      'inventory-db': { x: 420, y: 420 },
      'pricing-service': { x: 650, y: 280 },
      'payment-service': { x: 380, y: 530 },
      'payment-gateway': { x: 160, y: 530 },
      'order-service': { x: 620, y: 530 },
      'notification-service': { x: 620, y: 670 },
    };

    const nodes: Node[] = topology.nodes.map((n) => {
      const pos = positions[n.name] || {
        x: Math.random() * 600 + 100,
        y: Math.random() * 500 + 100,
      };

      return {
        id: n.id,
        type: 'serviceNode',
        position: pos,
        data: {
          node: n,
          isSelected: selectedServiceName === n.name,
        },
      };
    });

    const edges: Edge[] = topology.edges.map((e, idx) => {
      let strokeColor = '#10b981'; // emerald for HTTP_RPC
      let animated = true;

      if (e.relationship_type === 'CACHE_LOOKUP') {
        strokeColor = '#a855f7'; // purple
      } else if (e.relationship_type === 'DB_QUERY') {
        strokeColor = '#f59e0b'; // amber
      } else if (e.relationship_type === 'GATEWAY_CALL') {
        strokeColor = '#0284c7'; // sky
      }

      return {
        id: `edge-${idx}-${e.from_service}-${e.to_service}`,
        source: e.from_service,
        target: e.to_service,
        label: e.relationship_type,
        animated,
        style: { stroke: strokeColor, strokeWidth: 1.8 },
        labelStyle: { fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' },
        labelBgStyle: { fill: '#0f172a', fillOpacity: 0.9 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: strokeColor,
          width: 14,
          height: 14,
        },
      };
    });

    return { initialNodes: nodes, initialEdges: edges };
  }, [topology, selectedServiceName]);

  return (
    <div className="w-full h-[620px] rounded-xl border border-slate-800 bg-slate-950 relative overflow-hidden">
      <ReactFlow
        nodes={initialNodes}
        edges={initialEdges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onSelectService && onSelectService(node.id)}
        fitView
        className="bg-slate-950"
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1.2} color="#334155" />
        <Controls className="!bg-slate-900 !border-slate-800 !text-slate-300" />
      </ReactFlow>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 p-3 rounded-lg bg-slate-900/90 border border-slate-800/90 text-xs font-mono backdrop-blur space-y-1.5 shadow-lg">
        <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
          Dependency Types
        </div>
        <div className="flex items-center space-x-2 text-slate-300">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          <span>HTTP_RPC</span>
        </div>
        <div className="flex items-center space-x-2 text-slate-300">
          <span className="h-2 w-2 rounded-full bg-purple-500" />
          <span>CACHE_LOOKUP</span>
        </div>
        <div className="flex items-center space-x-2 text-slate-300">
          <span className="h-2 w-2 rounded-full bg-amber-500" />
          <span>DB_QUERY</span>
        </div>
        <div className="flex items-center space-x-2 text-slate-300">
          <span className="h-2 w-2 rounded-full bg-sky-500" />
          <span>GATEWAY_CALL</span>
        </div>
      </div>
    </div>
  );
};
