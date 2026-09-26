import React, { useState, useEffect, useCallback, useMemo } from 'react';
import CytoscapeComponent from 'react-cytoscapejs';
import { getTopologyGraph, discoverTopology } from '../services/api';
import { useToast } from '../hooks/useToast';

const LAYOUT = {
  name: 'cose',
  animate: false,
  padding: 30,
  nodeRepulsion: 8000,
  idealEdgeLength: 120,
};

const STYLESHEET = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'font-size': 10,
      color: '#c7d0e0',
      'text-valign': 'bottom',
      'text-margin-y': 4,
      width: 34,
      height: 34,
      'background-color': '#3b82f6',
      'border-width': 2,
      'border-color': '#1e293b',
    },
  },
  { selector: 'node[status = "down"]', style: { 'background-color': '#ef4444' } },
  { selector: 'node[status = "up"]', style: { 'background-color': '#22c55e' } },
  {
    selector: 'node[root = "yes"]',
    style: { shape: 'diamond', width: 44, height: 44, 'border-color': '#eab308' },
  },
  {
    selector: 'node[kind = "external"]',
    style: { 'background-color': '#64748b', shape: 'round-rectangle', 'border-style': 'dashed' },
  },
  {
    selector: 'edge',
    style: {
      width: 2,
      'line-color': '#475569',
      'curve-style': 'bezier',
      'target-arrow-shape': 'none',
      label: 'data(label)',
      'font-size': 8,
      color: '#7b8494',
      'text-rotation': 'autorotate',
    },
  },
  {
    selector: 'edge[kind = "external"]',
    style: { 'line-style': 'dashed', 'line-color': '#334155' },
  },
];

export default function TopologyMap() {
  const { showToast } = useToast();
  const [graph, setGraph] = useState({ nodes: [], edges: [], unresolved: [] });
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setGraph(await getTopologyGraph());
    } catch {
      showToast('Failed to load topology', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load();
  }, [load]);

  const handleDiscover = async () => {
    setDiscovering(true);
    try {
      const r = await discoverTopology();
      showToast(
        `Discovered ${r.edges} links across ${r.devices_walked} device(s)` +
          (r.timed_out ? `, ${r.timed_out} timed out` : ''),
        'success',
      );
      await load();
    } catch (err) {
      showToast('Discovery failed: ' + (err.response?.data?.detail || 'error'), 'error');
    } finally {
      setDiscovering(false);
    }
  };

  const elements = useMemo(() => {
    const isRoot = (tags) =>
      Array.isArray(tags) &&
      tags.some((t) => ['core', 'gateway'].includes(String(t).toLowerCase()));
    const nodes = graph.nodes.map((n) => ({
      data: {
        id: `d${n.id}`,
        label: n.name,
        status: n.status,
        root: isRoot(n.tags) ? 'yes' : 'no',
        kind: 'device',
      },
    }));
    const edges = graph.edges.map((e) => ({
      data: {
        id: `e${e.id}`,
        source: `d${e.source}`,
        target: `d${e.target}`,
        label: e.local_port || '',
        kind: 'device',
      },
    }));
    // Unresolved neighbours become external nodes so operators can see gaps.
    const extNodes = [];
    const extEdges = [];
    graph.unresolved.forEach((u) => {
      const extId = `x${u.id}`;
      extNodes.push({
        data: {
          id: extId,
          label: u.remote_sysname || u.remote_chassis_id || 'unknown',
          kind: 'external',
        },
      });
      extEdges.push({
        data: {
          id: `xe${u.id}`,
          source: `d${u.local_device_id}`,
          target: extId,
          label: u.local_port || '',
          kind: 'external',
        },
      });
    });
    return [...nodes, ...edges, ...extNodes, ...extEdges];
  }, [graph]);

  const hasData = graph.nodes.length > 0 && (graph.edges.length > 0 || graph.unresolved.length > 0);

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Topology Map</div>
          <div className="page-subtitle">
            LLDP-discovered network topology. Roots (core/gateway tag) shown as diamonds.
          </div>
        </div>
        <button className="btn btn-primary" onClick={handleDiscover} disabled={discovering}>
          {discovering ? 'Discovering…' : 'Discover topology'}
        </button>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-faint)' }}>
            Loading…
          </div>
        ) : !hasData ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-faint)' }}>
            No topology discovered yet. Click “Discover topology” to walk LLDP on all enabled
            devices.
          </div>
        ) : (
          <CytoscapeComponent
            elements={elements}
            layout={LAYOUT}
            stylesheet={STYLESHEET}
            style={{
              width: '100%',
              height: '640px',
              background: 'var(--color-bg-elevated, #0f1729)',
            }}
          />
        )}
      </div>

      {hasData && (
        <div
          className="card"
          style={{
            marginTop: 12,
            display: 'flex',
            gap: 20,
            fontSize: 12,
            color: 'var(--color-text-muted)',
            flexWrap: 'wrap',
          }}
        >
          <span>
            <span style={{ color: '#22c55e' }}>●</span> reachable
          </span>
          <span>
            <span style={{ color: '#ef4444' }}>●</span> unreachable
          </span>
          <span>
            <span style={{ color: '#eab308' }}>◆</span> root (core/gateway)
          </span>
          <span>
            <span style={{ color: '#64748b' }}>▭</span> unresolved neighbour
          </span>
        </div>
      )}
    </div>
  );
}
