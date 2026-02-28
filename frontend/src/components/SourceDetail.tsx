import { useState, useEffect } from "react";
import type { SourceRecord, SourceResource, RSSFeed } from "../types";
import type { ResourceAnalysis } from "../types";
import { getSourceResources, getFeedResources, getKnowledgeBases, addToKnowledgeBase, analyzeResource } from "../api";
import type { KnowledgeBase } from "../types";

type AnySource = (SourceRecord & { sourceKind: "unified" }) | (RSSFeed & { sourceKind: "rss" });

interface SourceDetailProps {
  source: AnySource | null;
  onRun: (sourceId: string) => void;
  onToggle: (source: AnySource) => void;
  onDelete: (sourceId: string) => void;
  actingSourceId: string | null;
  refreshKey?: number; // 用于触发资源刷新
}

export default function SourceDetail({ source, onRun, onToggle, onDelete, actingSourceId, refreshKey = 0 }: SourceDetailProps) {
  const [resources, setResources] = useState<SourceResource[]>([]);
  const [loadingResources, setLoadingResources] = useState(false);
  const [resourceError, setResourceError] = useState<string | null>(null);
  const [showKbModal, setShowKbModal] = useState(false);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const [addingToKb, setAddingToKb] = useState(false);
  const [analyzingIds, setAnalyzingIds] = useState<Set<string>>(new Set());
  const [analysisResults, setAnalysisResults] = useState<Record<string, ResourceAnalysis>>({});
  const [analysisErrors, setAnalysisErrors] = useState<Record<string, string>>({});
  const [expandedAnalysis, setExpandedAnalysis] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!source) {
      setResources([]);
      setResourceError(null);
      return;
    }

    const isRss = source.sourceKind === "rss";

    if (isRss) {
      const feedId = (source as RSSFeed).feed_id;
      setLoadingResources(true);
      setResourceError(null);
      getFeedResources(feedId, 80, 0)
        .then((data) => { console.log("[SourceDetail] getFeedResources result:", data.length, "items"); setResources(data); })
        .catch((e) => { console.error("[SourceDetail] getFeedResources error:", e); setResourceError(String(e)); setResources([]); })
        .finally(() => setLoadingResources(false));
      return;
    }

    const sourceId = (source as SourceRecord).source_id;
    setLoadingResources(true);
    setResourceError(null);
    getSourceResources(sourceId, 80, 0)
      .then((data) => { console.log("[SourceDetail] getSourceResources result:", data.length, "items"); setResources(data); })
      .catch((e) => { console.error("[SourceDetail] getSourceResources error:", e); setResourceError(String(e)); setResources([]); })
      .finally(() => setLoadingResources(false));
  }, [source, refreshKey]);

  async function openAddToKb(resourceId: string) {
    setSelectedResourceId(resourceId);
    try {
      const kbs = await getKnowledgeBases();
      setKnowledgeBases(kbs);
      setShowKbModal(true);
    } catch {
      // handle error
    }
  }

  async function handleAddResourceToKb(kbId: string) {
    if (!selectedResourceId) return;
    setAddingToKb(true);
    try {
      await addToKnowledgeBase(kbId, selectedResourceId);
      setShowKbModal(false);
      setSelectedResourceId(null);
    } catch {
      // handle error
    } finally {
      setAddingToKb(false);
    }
  }

  async function handleAnalyze(resourceId: string) {
    // 已有结果 → 切换展开
    if (analysisResults[resourceId]) {
      setExpandedAnalysis((prev) => {
        const next = new Set(prev);
        if (next.has(resourceId)) next.delete(resourceId);
        else next.add(resourceId);
        return next;
      });
      return;
    }

    setAnalyzingIds((prev) => new Set(prev).add(resourceId));
    setAnalysisErrors((prev) => { const n = { ...prev }; delete n[resourceId]; return n; });
    try {
      const result = await analyzeResource(resourceId);
      setAnalysisResults((prev) => ({ ...prev, [resourceId]: result }));
      setExpandedAnalysis((prev) => new Set(prev).add(resourceId));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "分析失败";
      setAnalysisErrors((prev) => ({ ...prev, [resourceId]: msg }));
    } finally {
      setAnalyzingIds((prev) => {
        const next = new Set(prev);
        next.delete(resourceId);
        return next;
      });
    }
  }

  if (!source) {
    return (
      <div className="source-detail-empty">
        <p>选择一个源查看详情</p>
      </div>
    );
  }

  const isRss = source.sourceKind === "rss";
  const unifiedSource = !isRss ? (source as SourceRecord) : null;
  const rssSource = isRss ? (source as RSSFeed) : null;

  const name = isRss ? rssSource!.name : unifiedSource!.name;
  const endpoint = isRss ? rssSource!.xml_url : unifiedSource!.endpoint;
  const enabled = isRss ? rssSource!.enabled : unifiedSource!.enabled;
  const errorCount = isRss ? rssSource!.error_count : unifiedSource!.error_count;
  const lastError = isRss ? rssSource!.last_error : unifiedSource!.last_error;
  const sourceType = isRss ? "rss" : unifiedSource!.source_type;
  const lastRunAt = isRss ? rssSource!.last_fetched_at : unifiedSource!.last_run_at;
  const sourceId = isRss ? rssSource!.feed_id : unifiedSource!.source_id;

  const isActing = actingSourceId === sourceId;

  function getTypeName(type: string): string {
    const names: Record<string, string> = {
      rss: "RSS 订阅",
      atom: "Atom 订阅",
      jsonfeed: "JSON Feed",
      academic_api: "学术 API",
      api: "REST API",
      api_json: "API JSON",
      api_xml: "API XML",
      web_page: "网页抓取",
      site_map: "站点地图",
      opml: "OPML 导入",
      jsonl: "JSONL 批量导入",
      manual_file: "本地文件",
    };
    return names[type] || type;
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleString("zh-CN");
  }

  return (
    <div className="source-detail">
      <div className="source-detail-header">
        <div className="source-detail-title">
          <h3>{name}</h3>
          <span className="source-detail-type">{getTypeName(sourceType)}</span>
        </div>
        <div className="source-detail-actions">
          <button
            className="icon-btn source-action-btn"
            onClick={() => onRun(sourceId)}
            disabled={isActing}
            title="立即运行"
          >
            ▶
          </button>
          <button
            className="icon-btn source-action-btn"
            onClick={() => onToggle(source)}
            disabled={isActing}
            title={enabled ? "暂停" : "启用"}
          >
            {enabled ? "⏸" : "▶"}
          </button>
          <button
            className="icon-btn source-action-btn danger"
            onClick={() => onDelete(sourceId)}
            disabled={isActing}
            title="删除"
          >
            🗑
          </button>
        </div>
      </div>

      <div className="source-detail-info">
        <div className="source-detail-row">
          <span className="source-detail-label">类型:</span>
          <span className="source-detail-value">{getTypeName(sourceType)}</span>
        </div>
        <div className="source-detail-row">
          <span className="source-detail-label">状态:</span>
          <span className={`source-detail-value ${enabled ? "status-enabled" : "status-disabled"}`}>
            {enabled ? "● 启用" : "○ 暂停"}
          </span>
        </div>
        <div className="source-detail-row">
          <span className="source-detail-label">上次运行:</span>
          <span className="source-detail-value">{formatDate(lastRunAt)}</span>
        </div>
        {errorCount > 0 && (
          <div className="source-detail-row">
            <span className="source-detail-label">错误:</span>
            <span className="source-detail-value source-detail-error">{errorCount} 次</span>
          </div>
        )}
        {lastError && (
          <div className="source-detail-error-msg">
            <span className="source-detail-label">错误信息:</span>
            <span className="source-detail-value">{lastError}</span>
          </div>
        )}
        {endpoint && (
          <div className="source-detail-row">
            <span className="source-detail-label">Endpoint:</span>
            <span className="source-detail-value source-detail-url">{endpoint}</span>
          </div>
        )}
      </div>

      <div className="source-detail-resources">
        <h4>最近抓取内容 {resources.length > 0 && `(${resources.length} 条)`}</h4>

        {loadingResources ? (
          <p className="source-detail-loading">加载中...</p>
        ) : resourceError ? (
          <p className="source-detail-hint" style={{ color: "var(--danger)" }}>
            加载失败：{resourceError}
          </p>
        ) : resources.length === 0 ? (
          <p className="source-detail-hint">暂无抓取结果，点击运行按钮开始抓取</p>
        ) : (
          <div className="source-resource-list">
            {resources.map((item) => (
              <article key={item.resource_id} className="source-resource-card">
                <div className="source-resource-card-header">
                  <a
                    href={item.original_url}
                    target="_blank"
                    rel="noreferrer"
                    className="source-resource-title"
                  >
                    {item.title}
                  </a>
                  <div className="source-resource-card-actions">
                    <button
                      className="add-btn add-btn-sm"
                      onClick={() => openAddToKb(item.resource_id)}
                      title="添加到知识库"
                    >
                      + 知识库
                    </button>
                    <button
                      className="add-btn add-btn-sm llm-analyze-btn"
                      onClick={() => handleAnalyze(item.resource_id)}
                      disabled={analyzingIds.has(item.resource_id)}
                      title="LLM 智能分析"
                    >
                      {analyzingIds.has(item.resource_id)
                        ? "分析中..."
                        : analysisResults[item.resource_id]
                          ? (expandedAnalysis.has(item.resource_id) ? "收起分析" : "查看分析")
                          : "LLM 总结"}
                    </button>
                  </div>
                </div>
                {item.summary && <p className="source-resource-summary">{item.summary}</p>}

                {/* 分析错误提示 */}
                {analysisErrors[item.resource_id] && (
                  <div className="analysis-error">
                    {analysisErrors[item.resource_id]}
                  </div>
                )}

                {/* 分析结果展开区 */}
                {expandedAnalysis.has(item.resource_id) && analysisResults[item.resource_id] && (() => {
                  const a = analysisResults[item.resource_id];
                  return (
                    <div className="analysis-result">
                      <div className="analysis-summary">
                        <strong>LLM 摘要：</strong>{a.summary}
                      </div>
                      {a.topics.length > 0 && (
                        <div className="analysis-topics">
                          {a.topics.map((t) => (
                            <span key={t} className="analysis-topic-badge">{t}</span>
                          ))}
                        </div>
                      )}
                      <div className="analysis-scores">
                        <span>深度 {a.scores.depth}/10</span>
                        <span>实用 {a.scores.utility}/10</span>
                        <span>新颖 {a.scores.novelty}/10</span>
                      </div>
                      <div className="analysis-meta">
                        tokens: {a.prompt_tokens + a.completion_tokens} ({a.prompt_tokens} + {a.completion_tokens})
                      </div>
                    </div>
                  );
                })()}

                <div className="source-resource-meta">
                  {item.topics.length > 0 && (
                    <span className="source-resource-tags">
                      {item.topics.map((t) => (
                        <span key={t} className="source-resource-tag">{t}</span>
                      ))}
                    </span>
                  )}
                  <span className="source-resource-date">
                    {item.last_seen_at ? formatDate(item.last_seen_at) : "-"}
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>

      {showKbModal && (
        <div className="modal-backdrop" onClick={() => setShowKbModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>选择知识库</h3>
            {knowledgeBases.length === 0 ? (
              <p>暂无知识库，请先在知识库页面创建。</p>
            ) : (
              <div className="kb-card-list">
                {knowledgeBases.map((kb) => (
                  <button
                    key={kb.kb_id}
                    className="kb-card"
                    onClick={() => handleAddResourceToKb(kb.kb_id)}
                    disabled={addingToKb}
                  >
                    <div className="kb-card-info">
                      <div className="kb-card-name">{kb.name}</div>
                      <div className="kb-card-desc">{kb.description ?? "无描述"}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
            <div className="modal-actions">
              <button onClick={() => setShowKbModal(false)}>关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}