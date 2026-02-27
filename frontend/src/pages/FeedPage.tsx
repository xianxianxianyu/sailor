import { useEffect, useState } from "react";
import {
  addToKnowledgeBase,
  addFeed,
  createSource,
  deleteFeed,
  deleteSource,
  getFeeds,
  getKnowledgeBases,
  getSourceResources,
  getSourceStatus,
  getSources,
  getUnifiedSourceStatus,
  importLocalSources,
  importOPML,
  runSource,
  runFeed,
  runIngestion,
  toggleFeed,
  updateSource,
} from "../api";
import type { KnowledgeBase, RSSFeed, SourceRecord, SourceResource, SourceStatus } from "../types";
import SourceList, { type AnySource, getSourceName } from "../components/SourceList";
import SourceDetail from "../components/SourceDetail";

type FeedOverviewStatus = {
  rss_total: number;
  rss_enabled: number;
  rss_errored: number;
  miniflux_configured: boolean;
  seed_file_exists: boolean;
};

interface FeedPageProps {
  onRequestShowLogs?: () => void;
}

export default function FeedPage({ onRequestShowLogs }: FeedPageProps) {
  const [feeds, setFeeds] = useState<RSSFeed[]>([]);
  const [feedStatus, setFeedStatus] = useState<FeedOverviewStatus | null>(null);

  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [sourceStatus, setSourceStatus] = useState<SourceStatus | null>(null);

  const [showAddFeed, setShowAddFeed] = useState(false);
  const [showAddSource, setShowAddSource] = useState(false);

  const [newFeedName, setNewFeedName] = useState("");
  const [newFeedUrl, setNewFeedUrl] = useState("");

  const [newSourceType, setNewSourceType] = useState("web_page");
  const [newSourceName, setNewSourceName] = useState("");
  const [newSourceEndpoint, setNewSourceEndpoint] = useState("");

  // 额外配置字段
  const [newSourceConfig, setNewSourceConfig] = useState<Record<string, string>>({});

  const [addingFeed, setAddingFeed] = useState(false);
  const [importingOPML, setImportingOPML] = useState(false);
  const [syncingConfig, setSyncingConfig] = useState(false);
  const [addingSource, setAddingSource] = useState(false);
  const [actingSourceId, setActingSourceId] = useState<string | null>(null);

  const [selectedSource, setSelectedSource] = useState<AnySource | null>(null);
  const [sourceRefreshKey, setSourceRefreshKey] = useState(0); // 用于刷新资源列表
  const [sourceResources, setSourceResources] = useState<SourceResource[]>([]);
  const [loadingSourceResources, setLoadingSourceResources] = useState(false);

  const [showKbModal, setShowKbModal] = useState(false);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const [addingToKb, setAddingToKb] = useState(false);

  const [message, setMessage] = useState("");

  // Combine feeds and sources into a single list
  const allSources: AnySource[] = [
    ...sources.map((s) => ({ ...s, sourceKind: "unified" as const })),
    ...feeds.map((f) => ({ ...f, sourceKind: "rss" as const })),
  ];

  async function load() {
    try {
      const [rssFeeds, rssStatus, unifiedSources, unifiedStatus] = await Promise.all([
        getFeeds(),
        getSourceStatus(),
        getSources(),
        getUnifiedSourceStatus(),
      ]);
      setFeeds(rssFeeds);
      setFeedStatus(rssStatus);
      setSources(unifiedSources);
      setSourceStatus(unifiedStatus);
    } catch {
      setMessage("加载订阅源失败，请检查后端服务");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleAddFeed() {
    if (!newFeedName.trim() || !newFeedUrl.trim()) return;
    setAddingFeed(true);
    try {
      await addFeed(newFeedName.trim(), newFeedUrl.trim());
      setNewFeedName("");
      setNewFeedUrl("");
      setShowAddFeed(false);
      await load();
      setMessage("RSS 源添加成功");
    } catch {
      setMessage("RSS 源添加失败，URL 可能已存在");
    } finally {
      setAddingFeed(false);
    }
  }

  async function handleImportOPML() {
    setImportingOPML(true);
    try {
      const result = await importOPML();
      setMessage(`OPML 导入完成：解析 ${result.total_parsed} 个，导入 ${result.imported} 个`);
      await load();
    } catch {
      setMessage("OPML 导入失败");
    } finally {
      setImportingOPML(false);
    }
  }

  async function handleSyncLocalConfig() {
    setSyncingConfig(true);
    try {
      const result = await importLocalSources();
      setMessage(
        `本地配置同步完成：解析 ${result.total_parsed} 条，写入 ${result.imported} 条，RSS 同步 ${result.rss_synced} 条`
      );
      await load();
    } catch {
      setMessage("本地配置同步失败，请检查 SailorRSSConfig.json");
    } finally {
      setSyncingConfig(false);
    }
  }

  async function handleRunAllIngestion() {
    // 打开日志面板
    onRequestShowLogs?.();
    setActingSourceId("all");
    try {
      const result = await runIngestion();
      setMessage(`一键抓取完成：抓取 ${result.collected_count} 条，处理 ${result.processed_count} 条`);
      await load();
    } catch {
      setMessage("抓取失败，请查看后端日志");
    } finally {
      setActingSourceId(null);
    }
  }

  async function handleDeleteFeed(feedId: string) {
    await deleteFeed(feedId);
    setSelectedSource(null);
    await load();
  }

  async function handleToggleFeed(feedId: string, enabled: boolean) {
    setActingSourceId(feedId);
    try {
      await toggleFeed(feedId, enabled);
      await load();
    } finally {
      setActingSourceId(null);
    }
  }

  async function handleAddSource() {
    if (!newSourceName.trim() || !newSourceEndpoint.trim()) return;
    setAddingSource(true);
    try {
      // 解析 config 中的 JSON 字段
      const config: Record<string, unknown> = { ...newSourceConfig };
      // 将字符串转为对象（如 headers）
      if (config.headers && typeof config.headers === "string") {
        try {
          config.headers = JSON.parse(config.headers as string);
        } catch {
          // 如果不是 JSON，就当作普通字符串
        }
      }

      await createSource({
        source_type: newSourceType,
        name: newSourceName.trim(),
        endpoint: newSourceEndpoint.trim(),
        config,
        enabled: true,
        schedule_minutes: 30,
      });
      setNewSourceName("");
      setNewSourceEndpoint("");
      setNewSourceConfig({});
      setShowAddSource(false);
      await load();
      setMessage("统一源添加成功");
    } catch {
      setMessage("统一源添加失败");
    } finally {
      setAddingSource(false);
    }
  }

  async function handleToggleSource(source: AnySource) {
    if (source.sourceKind === "rss") {
      await handleToggleFeed((source as RSSFeed).feed_id, !(source as RSSFeed).enabled);
    } else {
      const rec = source as SourceRecord;
      setActingSourceId(rec.source_id);
      try {
        await updateSource(rec.source_id, { enabled: !rec.enabled });
        await load();
      } finally {
        setActingSourceId(null);
      }
    }
  }

  async function handleDeleteSource(sourceId: string) {
    // Check if it's RSS or unified
    const isRss = selectedSource?.sourceKind === "rss";
    if (isRss) {
      await handleDeleteFeed(sourceId);
    } else {
      setActingSourceId(sourceId);
      try {
        await deleteSource(sourceId);
        setSelectedSource(null);
        await load();
      } finally {
        setActingSourceId(null);
      }
    }
  }

  async function handleRunSource(sourceId: string) {
    // Check if it's RSS
    const source = selectedSource;
    if (source?.sourceKind === "rss") {
      // Use runFeed for RSS sources
      setActingSourceId(sourceId);
      try {
        const result = await runFeed(sourceId);
        setMessage(`执行完成：抓取 ${result.fetched_count} 条，入库 ${result.processed_count} 条`);
        await load();
        // 刷新资源列表
        setSourceRefreshKey(prev => prev + 1);
      } catch {
        setMessage("执行 RSS 源失败，请查看后端日志");
      } finally {
        setActingSourceId(null);
      }
      return;
    }

    setActingSourceId(sourceId);
    try {
      const result = await runSource(sourceId);
      setMessage(`执行完成：抓取 ${result.fetched_count} 条，入库 ${result.processed_count} 条`);
      await load();
      // 刷新资源列表
      setSourceRefreshKey(prev => prev + 1);
    } catch {
      setMessage("执行源失败，请查看后端日志");
    } finally {
      setActingSourceId(null);
    }
  }

  function handleSelectSource(source: AnySource) {
    setSelectedSource(source);
  }

  return (
    <div className="page-content">
      <div className="feed-page-header">
        <h2>订阅源管理</h2>
        <div className="feed-page-actions">
          <div className="add-source-dropdown">
            <button
              onClick={() => setShowAddSource(!showAddSource)}
              className={`add-source-btn ${showAddSource ? "active" : ""}`}
              title="添加源"
            >
              +
            </button>
          </div>
        </div>
      </div>

      {message && (
        <p className="message">
          {message}
          <button className="message-close" onClick={() => setMessage("")}>
            ✕
          </button>
        </p>
      )}

      {(showAddFeed || showAddSource) && (
        <div className="feed-page-add-form">
          {showAddFeed && (
            <div className="create-form">
              <input
                value={newFeedName}
                onChange={(e) => setNewFeedName(e.target.value)}
                placeholder="源名称，如 Hacker News"
              />
              <input
                value={newFeedUrl}
                onChange={(e) => setNewFeedUrl(e.target.value)}
                placeholder="RSS URL，如 https://hnrss.org/frontpage"
              />
              <button onClick={handleAddFeed} disabled={addingFeed} className="add-btn">
                {addingFeed ? "添加中..." : "添加 RSS"}
              </button>
            </div>
          )}

          {showAddSource && (
            <div className="add-source-form">
              <div className="source-type-selector">
                <label>源类型：</label>
                <select value={newSourceType} onChange={(e) => setNewSourceType(e.target.value)}>
                  <option value="rss">RSS 订阅</option>
                  <option value="atom">Atom 订阅</option>
                  <option value="jsonfeed">JSON Feed</option>
                  <option value="academic_api">学术 API (arXiv/Scholar)</option>
                  <option value="api">REST API</option>
                  <option value="api_json">API JSON</option>
                  <option value="api_xml">API XML</option>
                  <option value="web_page">网页抓取</option>
                  <option value="site_map">站点地图</option>
                  <option value="opml">OPML 导入</option>
                  <option value="jsonl">JSONL 批量导入</option>
                  <option value="manual_file">本地文件</option>
                </select>
              </div>

              <div className="source-basic-fields">
                <input
                  value={newSourceName}
                  onChange={(e) => setNewSourceName(e.target.value)}
                  placeholder="源名称 *"
                  className="source-name-input"
                />
                <input
                  value={newSourceEndpoint}
                  onChange={(e) => setNewSourceEndpoint(e.target.value)}
                  placeholder={newSourceType === "opml" || newSourceType === "jsonl" || newSourceType === "manual_file" ? "文件路径" : "URL *"}
                  className="source-endpoint-input"
                />
              </div>

              {/* 动态配置字段 */}
              <div className="source-config-fields">
                {(newSourceType === "api" || newSourceType === "api_json" || newSourceType === "api_xml") && (
                  <>
                    <input
                      value={newSourceConfig.method || ""}
                      onChange={(e) => setNewSourceConfig({ ...newSourceConfig, method: e.target.value })}
                      placeholder="HTTP 方法 (GET/POST)"
                      className="config-input"
                    />
                    <input
                      value={newSourceConfig.headers || ""}
                      onChange={(e) => setNewSourceConfig({ ...newSourceConfig, headers: e.target.value })}
                      placeholder='Headers JSON, 如 {"Authorization": "Bearer xxx"}'
                      className="config-input"
                    />
                    {newSourceType === "api_json" && (
                      <>
                        <input
                          value={newSourceConfig.items_path || ""}
                          onChange={(e) => setNewSourceConfig({ ...newSourceConfig, items_path: e.target.value })}
                          placeholder="JSONPath 路径，如 data.items"
                          className="config-input"
                        />
                        <input
                          value={newSourceConfig.url_field || ""}
                          onChange={(e) => setNewSourceConfig({ ...newSourceConfig, url_field: e.target.value })}
                          placeholder="URL 字段名，如 url"
                          className="config-input"
                        />
                        <input
                          value={newSourceConfig.title_field || ""}
                          onChange={(e) => setNewSourceConfig({ ...newSourceConfig, title_field: e.target.value })}
                          placeholder="标题字段名，如 title"
                          className="config-input"
                        />
                      </>
                    )}
                  </>
                )}

                {newSourceType === "academic_api" && (
                  <>
                    <input
                      value={newSourceConfig.api_key || ""}
                      onChange={(e) => setNewSourceConfig({ ...newSourceConfig, api_key: e.target.value })}
                      placeholder="API Key (可选)"
                      className="config-input"
                    />
                    <input
                      value={newSourceConfig.search_query || ""}
                      onChange={(e) => setNewSourceConfig({ ...newSourceConfig, search_query: e.target.value })}
                      placeholder="搜索关键词，如 machine learning"
                      className="config-input"
                    />
                    <input
                      value={newSourceConfig.max_results || ""}
                      onChange={(e) => setNewSourceConfig({ ...newSourceConfig, max_results: e.target.value })}
                      placeholder="最大结果数，默认 20"
                      className="config-input"
                    />
                  </>
                )}

                {newSourceType === "web_page" && (
                  <input
                    value={newSourceConfig.selector || ""}
                    onChange={(e) => setNewSourceConfig({ ...newSourceConfig, selector: e.target.value })}
                    placeholder="CSS 选择器，如 .article-title"
                    className="config-input"
                  />
                )}

                {newSourceType === "api_xml" && (
                  <>
                    <input
                      value={newSourceConfig.items_path || ""}
                      onChange={(e) => setNewSourceConfig({ ...newSourceConfig, items_path: e.target.value })}
                      placeholder="XML 路径，如 channel/item"
                      className="config-input"
                    />
                    <input
                      value={newSourceConfig.url_field || ""}
                      onChange={(e) => setNewSourceConfig({ ...newSourceConfig, url_field: e.target.value })}
                      placeholder="URL 字段名"
                      className="config-input"
                    />
                    <input
                      value={newSourceConfig.title_field || ""}
                      onChange={(e) => setNewSourceConfig({ ...newSourceConfig, title_field: e.target.value })}
                      placeholder="标题字段名"
                      className="config-input"
                    />
                  </>
                )}
              </div>

              <div className="source-form-actions">
                <button onClick={handleAddSource} disabled={addingSource} className="add-btn">
                  {addingSource ? "添加中..." : "添加源"}
                </button>
                <button onClick={() => setShowAddSource(false)} className="cancel-btn">
                  取消
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {feedStatus && sourceStatus && (
        <div className="source-status-bar">
          <span className="status-item">
            📡 RSS: {feedStatus.rss_total} 个 ({feedStatus.rss_enabled} 启用
            {feedStatus.rss_errored > 0 && `, ${feedStatus.rss_errored} 异常`})
          </span>
          <span className="status-item">
            🗂 统一源: {sourceStatus.total} 条 ({sourceStatus.enabled} 启用
            {sourceStatus.errored > 0 && `, ${sourceStatus.errored} 异常`})
          </span>
          <span className="status-item">
            {feedStatus.miniflux_configured ? "✅ Miniflux 已配置" : "❌ Miniflux 未配置"}
          </span>
        </div>
      )}

      <div className="feed-page-layout">
        <div className="feed-page-left">
          <SourceList
            sources={allSources}
            selectedId={selectedSource ? (selectedSource.sourceKind === "rss" ? `rss-${(selectedSource as RSSFeed).feed_id}` : `unified-${(selectedSource as SourceRecord).source_id}`) : null}
            onSelect={handleSelectSource}
          />
        </div>
        <div className="feed-page-right">
          <SourceDetail
            source={selectedSource}
            onRun={handleRunSource}
            onToggle={handleToggleSource}
            onDelete={handleDeleteSource}
            actingSourceId={actingSourceId}
            refreshKey={sourceRefreshKey}
          />
        </div>
      </div>
    </div>
  );
}