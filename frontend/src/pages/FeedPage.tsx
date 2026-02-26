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
  toggleFeed,
  updateSource,
} from "../api";
import type { KnowledgeBase, RSSFeed, SourceRecord, SourceResource, SourceStatus } from "../types";

type FeedOverviewStatus = {
  rss_total: number;
  rss_enabled: number;
  rss_errored: number;
  miniflux_configured: boolean;
  seed_file_exists: boolean;
};

export default function FeedPage() {
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

  const [addingFeed, setAddingFeed] = useState(false);
  const [importingOPML, setImportingOPML] = useState(false);
  const [syncingConfig, setSyncingConfig] = useState(false);
  const [addingSource, setAddingSource] = useState(false);
  const [actingSourceId, setActingSourceId] = useState<string | null>(null);

  const [selectedSource, setSelectedSource] = useState<SourceRecord | null>(null);
  const [sourceResources, setSourceResources] = useState<SourceResource[]>([]);
  const [loadingSourceResources, setLoadingSourceResources] = useState(false);

  const [showKbModal, setShowKbModal] = useState(false);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const [addingToKb, setAddingToKb] = useState(false);

  const [message, setMessage] = useState("");

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

  async function handleDeleteFeed(feedId: string) {
    await deleteFeed(feedId);
    await load();
  }

  async function handleToggleFeed(feedId: string, enabled: boolean) {
    await toggleFeed(feedId, enabled);
    await load();
  }

  async function handleAddSource() {
    if (!newSourceName.trim() || !newSourceEndpoint.trim()) return;
    setAddingSource(true);
    try {
      await createSource({
        source_type: newSourceType,
        name: newSourceName.trim(),
        endpoint: newSourceEndpoint.trim(),
        config: {},
        enabled: true,
        schedule_minutes: 30,
      });
      setNewSourceName("");
      setNewSourceEndpoint("");
      setShowAddSource(false);
      await load();
      setMessage("统一源添加成功");
    } catch {
      setMessage("统一源添加失败");
    } finally {
      setAddingSource(false);
    }
  }

  async function handleToggleSource(source: SourceRecord) {
    setActingSourceId(source.source_id);
    try {
      await updateSource(source.source_id, { enabled: !source.enabled });
      await load();
    } finally {
      setActingSourceId(null);
    }
  }

  async function handleDeleteSource(sourceId: string) {
    setActingSourceId(sourceId);
    try {
      await deleteSource(sourceId);
      await load();
    } finally {
      setActingSourceId(null);
    }
  }

  async function handleRunSource(sourceId: string) {
    setActingSourceId(sourceId);
    try {
      const result = await runSource(sourceId);
      setMessage(`执行完成：抓取 ${result.fetched_count} 条，入库 ${result.processed_count} 条`);
      await load();
    } catch {
      setMessage("执行源失败，请查看后端日志");
    } finally {
      setActingSourceId(null);
    }
  }

  async function openSourceResources(source: SourceRecord) {
    setSelectedSource(source);
    setLoadingSourceResources(true);
    try {
      const items = await getSourceResources(source.source_id, 80, 0);
      setSourceResources(items);
    } catch {
      setMessage("加载源抓取内容失败");
      setSourceResources([]);
    } finally {
      setLoadingSourceResources(false);
    }
  }

  function closeSourceResources() {
    setSelectedSource(null);
    setSourceResources([]);
  }

  async function openAddToKb(resourceId: string) {
    setSelectedResourceId(resourceId);
    setAddingToKb(false);
    try {
      const kbs = await getKnowledgeBases();
      setKnowledgeBases(kbs);
      setShowKbModal(true);
    } catch {
      setMessage("加载知识库失败");
    }
  }

  async function handleAddResourceToKb(kbId: string) {
    if (!selectedResourceId) return;
    setAddingToKb(true);
    try {
      await addToKnowledgeBase(kbId, selectedResourceId);
      setMessage("已加入知识库");
      setShowKbModal(false);
      setSelectedResourceId(null);
    } catch {
      setMessage("加入知识库失败");
    } finally {
      setAddingToKb(false);
    }
  }

  return (
    <div className="page-content">
      <h2>订阅源管理</h2>

      <div className="feed-toolbar">
        <button onClick={handleImportOPML} disabled={importingOPML} className="add-btn">
          {importingOPML ? "导入中..." : "📄 导入 OPML"}
        </button>
        <button onClick={handleSyncLocalConfig} disabled={syncingConfig} className="add-btn">
          {syncingConfig ? "同步中..." : "🧩 同步 SailorRSSConfig.json"}
        </button>
        <button onClick={() => setShowAddFeed(!showAddFeed)} className="add-btn">
          {showAddFeed ? "取消" : "+ 添加 RSS 源"}
        </button>
        <button onClick={() => setShowAddSource(!showAddSource)} className="add-btn">
          {showAddSource ? "取消" : "+ 添加统一源"}
        </button>
      </div>

      {message && <p className="message">{message}</p>}

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
        <div className="create-form">
          <select value={newSourceType} onChange={(e) => setNewSourceType(e.target.value)}>
            <option value="web_page">web_page</option>
            <option value="manual_file">manual_file</option>
            <option value="api_json">api_json</option>
            <option value="site_map">site_map</option>
            <option value="rss">rss</option>
          </select>
          <input
            value={newSourceName}
            onChange={(e) => setNewSourceName(e.target.value)}
            placeholder="统一源名称"
          />
          <input
            value={newSourceEndpoint}
            onChange={(e) => setNewSourceEndpoint(e.target.value)}
            placeholder="endpoint，例如 URL 或本地文件路径"
          />
          <button onClick={handleAddSource} disabled={addingSource} className="add-btn">
            {addingSource ? "添加中..." : "添加统一源"}
          </button>
        </div>
      )}

      {feedStatus && (
        <div className="source-status-section">
          <h3>数据源状态</h3>
          <div className="source-status-grid">
            <div className="source-card">
              <span className="source-icon">📡</span>
              <div>
                <div className="source-name">RSS 订阅源</div>
                <div className="source-detail">
                  {feedStatus.rss_total} 个源，{feedStatus.rss_enabled} 个启用
                  {feedStatus.rss_errored > 0 && <span className="error-badge">，{feedStatus.rss_errored} 个异常</span>}
                </div>
              </div>
            </div>
            <div className="source-card">
              <span className="source-icon">🗂</span>
              <div>
                <div className="source-name">统一源注册表</div>
                <div className="source-detail">
                  {sourceStatus ? `${sourceStatus.total} 条，${sourceStatus.enabled} 条启用` : "加载中..."}
                  {sourceStatus && sourceStatus.errored > 0 && (
                    <span className="error-badge">，{sourceStatus.errored} 条异常</span>
                  )}
                </div>
              </div>
            </div>
            <div className="source-card">
              <span className="source-icon">🔗</span>
              <div>
                <div className="source-name">Miniflux (RSSHub)</div>
                <div className="source-detail">
                  {feedStatus.miniflux_configured ? "✅ 已配置" : "❌ 未配置（设置 MINIFLUX_BASE_URL 和 MINIFLUX_TOKEN）"}
                </div>
              </div>
            </div>
            <div className="source-card">
              <span className="source-icon">📁</span>
              <div>
                <div className="source-name">本地种子文件</div>
                <div className="source-detail">{feedStatus.seed_file_exists ? "✅ 存在" : "❌ 不存在"}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="feed-table-section">
        <h3>统一源列表 ({sources.length})</h3>
        {sources.length === 0 ? (
          <div className="empty-guide">
            <p>还没有统一源。可先点击“同步 SailorRSSConfig.json”。</p>
          </div>
        ) : (
          <table className="feed-table">
            <thead>
              <tr>
                <th>类型</th>
                <th>名称</th>
                <th>Endpoint</th>
                <th>状态</th>
                <th>错误</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => (
                <tr key={source.source_id} className={!source.enabled ? "feed-disabled" : ""}>
                  <td>{source.source_type}</td>
                  <td>
                    <button className="source-name-link" onClick={() => openSourceResources(source)}>
                      {source.name}
                    </button>
                  </td>
                  <td className="feed-url">{source.endpoint ?? "-"}</td>
                  <td>{source.enabled ? "✅" : "⏸️"}</td>
                  <td>{source.error_count > 0 ? `${source.error_count}次` : "-"}</td>
                  <td className="feed-actions">
                    <button
                      className="icon-btn"
                      onClick={() => handleRunSource(source.source_id)}
                      disabled={actingSourceId === source.source_id}
                      title="立即运行"
                    >
                      ▶
                    </button>
                    <button
                      className="icon-btn"
                      onClick={() => handleToggleSource(source)}
                      disabled={actingSourceId === source.source_id}
                      title={source.enabled ? "暂停" : "启用"}
                    >
                      {source.enabled ? "⏸" : "⏯"}
                    </button>
                    <button
                      className="icon-btn danger"
                      onClick={() => handleDeleteSource(source.source_id)}
                      disabled={actingSourceId === source.source_id}
                      title="删除"
                    >
                      🗑
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="feed-table-section">
        <h3>RSS 订阅源 ({feeds.length})</h3>
        {feeds.length === 0 ? (
          <div className="empty-guide">
            <p>还没有 RSS 源。导入 OPML 文件或手动添加 RSS URL。</p>
          </div>
        ) : (
          <table className="feed-table">
            <thead>
              <tr>
                <th>状态</th>
                <th>名称</th>
                <th>URL</th>
                <th>错误</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {feeds.map((feed) => (
                <tr key={feed.feed_id} className={!feed.enabled ? "feed-disabled" : ""}>
                  <td>{!feed.enabled ? "⏸️" : feed.error_count > 0 ? "⚠️" : "✅"}</td>
                  <td>{feed.name}</td>
                  <td className="feed-url">{feed.xml_url}</td>
                  <td>{feed.error_count > 0 ? `${feed.error_count}次` : "-"}</td>
                  <td className="feed-actions">
                    <button
                      className="icon-btn"
                      onClick={() => handleToggleFeed(feed.feed_id, !feed.enabled)}
                      title={feed.enabled ? "暂停" : "启用"}
                    >
                      {feed.enabled ? "⏸" : "▶"}
                    </button>
                    <button
                      className="icon-btn danger"
                      onClick={() => handleDeleteFeed(feed.feed_id)}
                      title="删除"
                      aria-label={`删除 ${feed.name}`}
                    >
                      🗑
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selectedSource && (
        <div className="modal-backdrop" onClick={closeSourceResources}>
          <div className="source-resource-modal" onClick={(e) => e.stopPropagation()}>
            <div className="source-resource-header">
              <h3>{selectedSource.name} · 抓取内容</h3>
              <button className="icon-btn" onClick={closeSourceResources} title="关闭">
                ✕
              </button>
            </div>

            {loadingSourceResources ? (
              <p>加载中...</p>
            ) : sourceResources.length === 0 ? (
              <p className="source-resource-empty">暂无抓取结果，先点击“立即运行”。</p>
            ) : (
              <div className="source-resource-list">
                {sourceResources.map((item) => (
                  <article key={item.resource_id} className="source-resource-card">
                    <div className="source-resource-card-header">
                      <a href={item.original_url} target="_blank" rel="noreferrer" className="source-resource-title">
                        {item.title}
                      </a>
                      <button className="add-btn" onClick={() => openAddToKb(item.resource_id)}>
                        + 加入知识库
                      </button>
                    </div>
                    {item.summary && <p className="source-resource-summary">{item.summary}</p>}
                    <div className="source-resource-meta">
                      <span>最近抓取：{item.last_seen_at ?? "-"}</span>
                      {item.topics.length > 0 && (
                        <span className="source-resource-topics">标签：{item.topics.join(" / ")}</span>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

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
