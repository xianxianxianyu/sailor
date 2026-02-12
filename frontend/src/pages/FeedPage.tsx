import { useEffect, useState } from "react";
import {
  addFeed,
  deleteFeed,
  getFeeds,
  getSourceStatus,
  importOPML,
  toggleFeed,
} from "../api";
import type { RSSFeed } from "../types";

type SourceStatus = {
  rss_total: number;
  rss_enabled: number;
  rss_errored: number;
  miniflux_configured: boolean;
  seed_file_exists: boolean;
};

export default function FeedPage() {
  const [feeds, setFeeds] = useState<RSSFeed[]>([]);
  const [status, setStatus] = useState<SourceStatus | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);
  const [message, setMessage] = useState("");

  async function load() {
    const [f, s] = await Promise.all([getFeeds(), getSourceStatus()]);
    setFeeds(f);
    setStatus(s);
  }

  useEffect(() => { load(); }, []);

  async function handleAdd() {
    if (!newName.trim() || !newUrl.trim()) return;
    setAdding(true);
    try {
      await addFeed(newName.trim(), newUrl.trim());
      setNewName(""); setNewUrl(""); setShowAdd(false);
      await load();
      setMessage("添加成功");
    } catch {
      setMessage("添加失败，URL 可能已存在");
    } finally {
      setAdding(false);
    }
  }

  async function handleImport() {
    setImporting(true);
    try {
      const result = await importOPML();
      setMessage(`导入完成：解析 ${result.total_parsed} 个，导入 ${result.imported} 个`);
      await load();
    } catch {
      setMessage("OPML 导入失败");
    } finally {
      setImporting(false);
    }
  }

  async function handleDelete(feedId: string) {
    await deleteFeed(feedId);
    await load();
  }

  async function handleToggle(feedId: string, enabled: boolean) {
    await toggleFeed(feedId, enabled);
    await load();
  }

  return (
    <div className="page-content">
      <h2>订阅源管理</h2>

      {/* 快捷操作 */}
      <div className="feed-toolbar">
        <button onClick={handleImport} disabled={importing} className="add-btn">
          {importing ? "导入中..." : "📄 导入 OPML"}
        </button>
        <button onClick={() => setShowAdd(!showAdd)} className="add-btn">
          {showAdd ? "取消" : "+ 添加 RSS 源"}
        </button>
      </div>

      {message && <p className="message">{message}</p>}

      {/* 添加表单 */}
      {showAdd && (
        <div className="create-form">
          <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="源名称，如 Hacker News" />
          <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="RSS URL，如 https://hnrss.org/frontpage" />
          <button onClick={handleAdd} disabled={adding} className="add-btn">
            {adding ? "添加中..." : "添加"}
          </button>
        </div>
      )}

      {/* 非 RSS 源状态 */}
      {status && (
        <div className="source-status-section">
          <h3>数据源状态</h3>
          <div className="source-status-grid">
            <div className="source-card">
              <span className="source-icon">📡</span>
              <div>
                <div className="source-name">RSS 订阅源</div>
                <div className="source-detail">
                  {status.rss_total} 个源，{status.rss_enabled} 个启用
                  {status.rss_errored > 0 && <span className="error-badge">，{status.rss_errored} 个异常</span>}
                </div>
              </div>
            </div>
            <div className="source-card">
              <span className="source-icon">🔗</span>
              <div>
                <div className="source-name">Miniflux (RSSHub)</div>
                <div className="source-detail">
                  {status.miniflux_configured ? "✅ 已配置" : "❌ 未配置（设置 MINIFLUX_BASE_URL 和 MINIFLUX_TOKEN）"}
                </div>
              </div>
            </div>
            <div className="source-card">
              <span className="source-icon">📁</span>
              <div>
                <div className="source-name">本地种子文件</div>
                <div className="source-detail">
                  {status.seed_file_exists ? "✅ 存在" : "❌ 不存在"}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* RSS Feed 列表 */}
      <div className="feed-table-section">
        <h3>RSS 订阅源 ({feeds.length})</h3>
        {feeds.length === 0 ? (
          <div className="empty-guide">
            <p>还没有订阅源。导入 OPML 文件或手动添加 RSS URL。</p>
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
                  <td>
                    {!feed.enabled ? "⏸️" : feed.error_count > 0 ? "⚠️" : "✅"}
                  </td>
                  <td>{feed.name}</td>
                  <td className="feed-url">{feed.xml_url}</td>
                  <td>{feed.error_count > 0 ? `${feed.error_count}次` : "-"}</td>
                  <td className="feed-actions">
                    <button
                      className="icon-btn"
                      onClick={() => handleToggle(feed.feed_id, !feed.enabled)}
                      title={feed.enabled ? "暂停" : "启用"}
                    >{feed.enabled ? "⏸" : "▶"}</button>
                    <button
                      className="icon-btn danger"
                      onClick={() => handleDelete(feed.feed_id)}
                      title="删除"
                      aria-label={`删除 ${feed.name}`}
                    >🗑</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
