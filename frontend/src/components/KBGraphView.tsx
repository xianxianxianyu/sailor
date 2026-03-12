import { useEffect, useRef, useState, useCallback } from "react";
import ForceGraph2D from "react-force-graph-2d";
import {
  deleteKBGraphEdge,
  freezeKBGraphEdge,
  unfreezeKBGraphEdge,
  createKBGraphEdge,
  getKBGraph,
  getKBGraphNode,
  relinkKBGraphNode,
  getKBGraphHistory,
} from "../api";
import type { KGEdge, KGGraph, KGNode, KGNodeDetail } from "../types";

export default function KBGraphView({ kbId }: { kbId: string }) {
  const [graph, setGraph] = useState<KGGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<KGNodeDetail | null>(null);
  const [viewMode, setViewMode] = useState<"full" | "local">("full");
  const [startNodeId, setStartNodeId] = useState<string | null>(null);
  const [showAddEdgeDialog, setShowAddEdgeDialog] = useState(false);
  const [newEdge, setNewEdge] = useState({
    targetNodeId: "",
    reason: "",
    reasonType: "related_topic",
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [relinking, setRelinking] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoading(true);
    setSelectedNode(null);
    const params =
      viewMode === "local" && startNodeId
        ? { mode: "local" as const, start_node_id: startNodeId, depth: 2 }
        : { mode: "full" as const, limit: 200 };

    getKBGraph(kbId, params)
      .then(setGraph)
      .catch(() => setGraph(null))
      .finally(() => setLoading(false));
  }, [kbId, viewMode, startNodeId]);

  const handleNodeClick = useCallback(
    async (node: KGNode) => {
      setCurrentPage(1);
      const detail = await getKBGraphNode(kbId, node.id, 1, 50);
      setSelectedNode(detail);
    },
    [kbId]
  );

  async function handleDeleteEdge(edge: KGEdge) {
    setGraph((g) => (g ? { ...g, edges: g.edges.filter((e) => e !== edge) } : g));
    setSelectedNode((n) =>
      n ? { ...n, neighbors: n.neighbors.filter((nb) => nb.edge !== edge) } : n
    );
    try {
      await deleteKBGraphEdge(kbId, edge.node_a_id, edge.node_b_id);
    } catch {
      const params =
        viewMode === "local" && startNodeId
          ? { mode: "local" as const, start_node_id: startNodeId, depth: 2 }
          : { mode: "full" as const, limit: 200 };
      const fresh = await getKBGraph(kbId, params);
      setGraph(fresh);
    }
  }

  async function handleToggleFreeze(edge: KGEdge) {
    try {
      if (edge.frozen) {
        await unfreezeKBGraphEdge(kbId, edge.node_a_id, edge.node_b_id);
      } else {
        await freezeKBGraphEdge(kbId, edge.node_a_id, edge.node_b_id);
      }
      if (selectedNode) {
        const detail = await getKBGraphNode(kbId, selectedNode.node.id, currentPage, 50);
        setSelectedNode(detail);
      }
      const params =
        viewMode === "local" && startNodeId
          ? { mode: "local" as const, start_node_id: startNodeId, depth: 2 }
          : { mode: "full" as const, limit: 200 };
      const fresh = await getKBGraph(kbId, params);
      setGraph(fresh);
    } catch (error) {
      console.error("Failed to toggle freeze:", error);
      alert("操作失败，请重试");
    }
  }

  async function handleCreateEdge() {
    if (!selectedNode || !newEdge.targetNodeId || !newEdge.reason) {
      alert("请填写完整信息");
      return;
    }

    try {
      await createKBGraphEdge(kbId, {
        node_a_id: selectedNode.node.id,
        node_b_id: newEdge.targetNodeId,
        reason: newEdge.reason,
        reason_type: newEdge.reasonType,
      });

      const detail = await getKBGraphNode(kbId, selectedNode.node.id, currentPage, 50);
      setSelectedNode(detail);
      const params =
        viewMode === "local" && startNodeId
          ? { mode: "local" as const, start_node_id: startNodeId, depth: 2 }
          : { mode: "full" as const, limit: 200 };
      const fresh = await getKBGraph(kbId, params);
      setGraph(fresh);

      setShowAddEdgeDialog(false);
      setNewEdge({ targetNodeId: "", reason: "", reasonType: "related_topic" });
    } catch (error) {
      console.error("Failed to create edge:", error);
      alert("创建连接失败");
    }
  }

  async function handlePageChange(newPage: number) {
    if (!selectedNode) return;
    setCurrentPage(newPage);
    const detail = await getKBGraphNode(kbId, selectedNode.node.id, newPage, 50);
    setSelectedNode(detail);
  }

  async function handleRelink() {
    if (!selectedNode || relinking) return;
    setRelinking(true);
    try {
      await relinkKBGraphNode(kbId, selectedNode.node.id);
      alert("重新连边任务已提交，请稍后刷新查看结果");
    } catch (error) {
      console.error("Failed to relink:", error);
      alert("重新连边失败");
    } finally {
      setRelinking(false);
    }
  }

  const graphData = {
    nodes: graph?.nodes ?? [],
    links: graph?.edges ?? [],
  };

  const totalNeighbors = selectedNode?.total_neighbors ?? selectedNode?.neighbors.length ?? 0;
  const pageSize = selectedNode?.page_size ?? 50;
  const totalPages = Math.ceil(totalNeighbors / pageSize);

  return (
    <div className="kb-graph-view">
      <div className="graph-view-controls">
        <button
          className={viewMode === "full" ? "active" : ""}
          onClick={() => {
            setViewMode("full");
            setStartNodeId(null);
          }}
        >
          全图视图
        </button>
        <button
          className={viewMode === "local" ? "active" : ""}
          onClick={() => setViewMode("local")}
        >
          局部视图
        </button>
        <button
          className="graph-tool-btn"
          onClick={() => setShowHistory(true)}
        >
          📜 历史
        </button>

        {viewMode === "local" && (
          <select
            value={startNodeId || ""}
            onChange={(e) => setStartNodeId(e.target.value)}
            className="start-node-select"
          >
            <option value="">选择起点节点</option>
            {graph?.nodes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.title}
              </option>
            ))}
          </select>
        )}

        {graph && graph.nodes.length >= 200 && viewMode === "full" && (
          <div className="warning">⚠️ 节点数达到 200 上限，建议切换到局部视图</div>
        )}
      </div>

      <div className="kb-graph-content" ref={containerRef}>
        <div className="kb-graph-canvas">
          {loading ? (
            <div className="kg-loading">Loading graph…</div>
          ) : graph?.nodes.length === 0 ? (
            <div className="kg-empty">此 KB 暂无资源。先收藏一些文章再查看图。</div>
          ) : (
            <ForceGraph2D
              graphData={graphData}
              nodeLabel="title"
              nodeAutoColorBy="id"
              onNodeClick={handleNodeClick}
              width={
                containerRef.current?.clientWidth
                  ? containerRef.current.clientWidth * 0.65
                  : 600
              }
              height={500}
            />
          )}
        </div>

        {selectedNode && (
          <div className="kb-graph-sidebar">
            <div className="kg-sidebar-header">
              <span className="kg-node-title">{selectedNode.node.title}</span>
              <button className="kg-close-btn" onClick={() => setSelectedNode(null)}>
                ✕
              </button>
            </div>
            <p className="kg-node-summary">{selectedNode.node.summary}</p>
            <a
              href={selectedNode.node.url}
              target="_blank"
              rel="noopener noreferrer"
              className="kg-node-link"
            >
              原文链接 ↗
            </a>

            <div className="kg-neighbors-header">
              <div className="kg-neighbors-title">邻接节点 ({totalNeighbors})</div>
              <div className="kg-neighbors-actions">
                <button
                  className="kg-relink-btn"
                  onClick={handleRelink}
                  disabled={relinking}
                  title="使用 AI 重新推理此节点的连接"
                >
                  {relinking ? "处理中..." : "🔄 重新连边"}
                </button>
                <button
                  className="kg-add-edge-btn"
                  onClick={() => setShowAddEdgeDialog(true)}
                >
                  + 添加连接
                </button>
              </div>
            </div>

            {selectedNode.neighbors.length === 0 ? (
              <div className="kg-empty-neighbors">暂无连边。可手动连边。</div>
            ) : (
              <>
                <ul className="kg-neighbor-list">
                  {selectedNode.neighbors.map(({ node, edge }) => (
                    <NeighborItem
                      key={node.id}
                      node={node}
                      edge={edge}
                      onDelete={handleDeleteEdge}
                      onToggleFreeze={handleToggleFreeze}
                    />
                  ))}
                </ul>

                {totalPages > 1 && (
                  <div className="kg-pagination">
                    <button
                      disabled={currentPage === 1}
                      onClick={() => handlePageChange(currentPage - 1)}
                    >
                      上一页
                    </button>
                    <span>
                      第 {currentPage} / {totalPages} 页
                    </span>
                    <button
                      disabled={currentPage >= totalPages}
                      onClick={() => handlePageChange(currentPage + 1)}
                    >
                      下一页
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {showAddEdgeDialog && (
        <div className="kg-dialog-overlay" onClick={() => setShowAddEdgeDialog(false)}>
          <div className="kg-add-edge-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>添加连接</h3>
            <label>
              目标节点：
              <select
                value={newEdge.targetNodeId}
                onChange={(e) =>
                  setNewEdge({ ...newEdge, targetNodeId: e.target.value })
                }
              >
                <option value="">选择节点</option>
                {graph?.nodes
                  .filter((n) => n.id !== selectedNode?.node.id)
                  .map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.title}
                    </option>
                  ))}
              </select>
            </label>

            <label>
              连接理由：
              <textarea
                value={newEdge.reason}
                onChange={(e) => setNewEdge({ ...newEdge, reason: e.target.value })}
                placeholder="说明为什么这两个节点应该连接..."
                rows={4}
              />
            </label>

            <label>
              连接类型：
              <select
                value={newEdge.reasonType}
                onChange={(e) =>
                  setNewEdge({ ...newEdge, reasonType: e.target.value })
                }
              >
                <option value="related_topic">相关主题</option>
                <option value="citation">引用关系</option>
                <option value="contradiction">观点冲突</option>
                <option value="extension">扩展/深化</option>
                <option value="example">示例关系</option>
                <option value="comparison">对比关系</option>
                <option value="prerequisite">前置知识</option>
                <option value="application">应用关系</option>
              </select>
            </label>

            <div className="kg-dialog-actions">
              <button onClick={handleCreateEdge}>创建</button>
              <button onClick={() => setShowAddEdgeDialog(false)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {showHistory && (
        <div className="kg-dialog-overlay" onClick={() => setShowHistory(false)}>
          <div className="kg-add-edge-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>知识图谱操作历史</h3>
            <KBGraphHistory kbId={kbId} />
            <div className="kg-dialog-actions">
              <button onClick={() => setShowHistory(false)}>关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function NeighborItem({
  node,
  edge,
  onDelete,
  onToggleFreeze,
}: {
  node: KGNode;
  edge: KGEdge;
  onDelete: (edge: KGEdge) => void;
  onToggleFreeze: (edge: KGEdge) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const reason = edge.reason || "—";
  const needsExpand = reason.length > 100;
  const displayReason = expanded || !needsExpand ? reason : reason.slice(0, 100) + "...";

  return (
    <li className="kg-neighbor-item">
      <div className="kg-neighbor-header">
        <span className="kg-neighbor-name">{node.title}</span>
        {edge.frozen === 1 && <span className="kg-frozen-icon">🔒</span>}
        {edge.reason_type && (
          <span className={`kg-reason-type-tag ${edge.reason_type}`}>
            {edge.reason_type}
          </span>
        )}
      </div>
      <div className="kg-neighbor-reason">
        {displayReason}
        {needsExpand && (
          <button
            className="kg-expand-btn"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "收起" : "展开"}
          </button>
        )}
      </div>
      <div className="kg-neighbor-actions">
        <button
          className={`kg-freeze-btn ${edge.frozen ? "frozen" : ""}`}
          onClick={() => onToggleFreeze(edge)}
          title={edge.frozen ? "解冻" : "冻结"}
        >
          {edge.frozen ? "🔒" : "🔓"}
        </button>
        <button
          className="kg-delete-btn"
          onClick={() => onDelete(edge)}
          disabled={edge.frozen === 1}
          title="删除该边"
        >
          删除
        </button>
      </div>
    </li>
  );
}

function KBGraphHistory({ kbId }: { kbId: string }) {
  const [history, setHistory] = useState<Array<{
    job_id: string;
    job_type: string;
    status: string;
    node_id: string;
    created_at: string | null;
    finished_at: string | null;
    output: string | null;
  }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadHistory();
  }, [kbId]);

  async function loadHistory() {
    setLoading(true);
    try {
      const data = await getKBGraphHistory(kbId, 50);
      setHistory(data.jobs || []);
    } catch (error) {
      console.error("Failed to load history:", error);
      setHistory([]);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return <div className="kg-history-loading">加载中...</div>;
  }

  if (history.length === 0) {
    return <div className="kg-history-empty">暂无操作历史</div>;
  }

  return (
    <div className="kg-history">
      {history.map((job) => (
        <div key={job.job_id} className="kg-history-item">
          <div className="kg-history-header">
            <span className="kg-history-type">{job.job_type}</span>
            <span className={`kg-history-status ${job.status}`}>{job.status}</span>
          </div>
          <div className="kg-history-meta">
            <span>节点: {job.node_id}</span>
            <span>{job.created_at ? new Date(job.created_at).toLocaleString() : "—"}</span>
          </div>
          {job.output && (
            <div className="kg-history-output">{job.output}</div>
          )}
        </div>
      ))}
    </div>
  );
}
