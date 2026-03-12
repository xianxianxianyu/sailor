import { useEffect, useState } from "react";
import {
  cancelJob,
  createSource,
  deleteSource,
  getSources,
  getUnifiedSourceStatus,
  importLocalSources,
  importOpmlToSources,
  JobCancelledError,
  JobFailedError,
  JobTimeoutError,
  runSource,
  assertJobSucceeded,
  updateSource,
  waitForJob,
} from "../api";
import type { SourceRecord, SourceResource, SourceStatus } from "../types";
import SourceList, { getSourceName } from "../components/SourceList";
import SourceDetail from "../components/SourceDetail";

interface FeedPageProps {
  onRequestShowLogs?: () => void;
}

export default function FeedPage({ onRequestShowLogs: _onRequestShowLogs }: FeedPageProps) {
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [sourceStatus, setSourceStatus] = useState<SourceStatus | null>(null);

  const [showAddSource, setShowAddSource] = useState(false);

  const [newSourceType, setNewSourceType] = useState("rss");
  const [newSourceName, setNewSourceName] = useState("");
  const [newSourceEndpoint, setNewSourceEndpoint] = useState("");
  const [newSourceConfig, setNewSourceConfig] = useState<Record<string, string>>({});

  const [importingOPML, setImportingOPML] = useState(false);
  const [syncingConfig, setSyncingConfig] = useState(false);
  const [addingSource, setAddingSource] = useState(false);
  const [actingSourceIds, setActingSourceIds] = useState<Set<string>>(new Set());

  const [selectedSource, setSelectedSource] = useState<SourceRecord | null>(null);
  const [sourceRefreshKey, setSourceRefreshKey] = useState(0);
  const [sourceResources] = useState<SourceResource[]>([]);
  const [activeRunJobs, setActiveRunJobs] = useState<Record<string, string>>({});
  const [cancellingJobIds, setCancellingJobIds] = useState<Set<string>>(new Set());

  const [message, setMessage] = useState("");

  function startActing(sourceId: string) {
    setActingSourceIds((prev) => new Set(prev).add(sourceId));
  }

  function stopActing(sourceId: string) {
    setActingSourceIds((prev) => {
      const next = new Set(prev);
      next.delete(sourceId);
      return next;
    });
  }

  function rememberActiveRun(sourceId: string, jobId: string) {
    setActiveRunJobs((prev) => ({ ...prev, [sourceId]: jobId }));
  }

  function clearActiveRun(sourceId: string) {
    setActiveRunJobs((prev) => {
      const next = { ...prev };
      delete next[sourceId];
      return next;
    });
  }

  async function load() {
    try {
      const [unifiedSources, unifiedStatus] = await Promise.all([
        getSources(),
        getUnifiedSourceStatus(),
      ]);
      setSources(unifiedSources);
      setSourceStatus(unifiedStatus);
    } catch {
      setMessage("加载订阅源失败，请检查后端服务");
    }
  }

  useEffect(() => {
    load();
  }, []);

  // suppress unused warning
  void sourceResources;

  async function handleImportOPML() {
    setImportingOPML(true);
    try {
      const result = await importOpmlToSources();
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
      setMessage(`本地配置同步完成：解析 ${result.total_parsed} 条，写入 ${result.imported} 条`);
      await load();
    } catch {
      setMessage("本地配置同步失败，请检查 SailorRSSConfig.json");
    } finally {
      setSyncingConfig(false);
    }
  }

  async function handleAddSource() {
    if (!newSourceName.trim() || !newSourceEndpoint.trim()) return;
    setAddingSource(true);
    try {
      const config: Record<string, unknown> = { ...newSourceConfig };
      if (config.headers && typeof config.headers === "string") {
        try {
          config.headers = JSON.parse(config.headers as string);
        } catch {
          // keep as string if not valid JSON
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
      setMessage("源添加成功");
    } catch {
      setMessage("源添加失败");
    } finally {
      setAddingSource(false);
    }
  }

  async function handleToggleSource(source: SourceRecord) {
    startActing(source.source_id);
    try {
      await updateSource(source.source_id, { enabled: !source.enabled });
      await load();
    } finally {
      stopActing(source.source_id);
    }
  }

  async function handleDeleteSource(sourceId: string) {
    startActing(sourceId);
    try {
      await deleteSource(sourceId);
      setSelectedSource(null);
      await load();
    } finally {
      stopActing(sourceId);
    }
  }

  async function handleRunSource(sourceId: string) {
    startActing(sourceId);
    let shouldClearActiveRun = true;
    try {
      const accepted = await runSource(sourceId, { wait: true, timeoutSec: 60 });
      if (!accepted.job_id) {
        setMessage(`已触发运行，但后端未返回 job_id（status=${accepted.status}）`);
        return;
      }

      rememberActiveRun(sourceId, accepted.job_id);
      shouldClearActiveRun = false;

      if (accepted.status === "succeeded") {
        shouldClearActiveRun = true;
        setMessage(`执行完成：抓取 ${accepted.fetched_count} 条，入库 ${accepted.processed_count} 条（job_id=${accepted.job_id}）`);
        await load();
        setSourceRefreshKey((prev) => prev + 1);
        return;
      }

      if (accepted.status === "failed") {
        shouldClearActiveRun = true;
        setMessage(`执行失败：${accepted.error_message ?? "未知错误"}（job_id=${accepted.job_id}）`);
        return;
      }

      if (accepted.status === "cancelled") {
        shouldClearActiveRun = true;
        setMessage(`运行已取消（job_id=${accepted.job_id}）`);
        return;
      }

      setMessage(`后台运行中：status=${accepted.status}，job_id=${accepted.job_id}（将自动刷新）`);

      const job = await waitForJob(accepted.job_id, 600_000, 1_000);
      assertJobSucceeded(job);
      shouldClearActiveRun = true;

      let fetched = 0;
      let processed = 0;
      try {
        const output = JSON.parse(job.output_json ?? "{}") as { fetched_count?: number; processed_count?: number };
        fetched = typeof output.fetched_count === "number" ? output.fetched_count : 0;
        processed = typeof output.processed_count === "number" ? output.processed_count : 0;
      } catch {
        // ignore parse errors
      }

      setMessage(`执行完成：抓取 ${fetched} 条，入库 ${processed} 条（job_id=${accepted.job_id}）`);
      await load();
      setSourceRefreshKey((prev) => prev + 1);
    } catch (e: unknown) {
      if (e instanceof JobTimeoutError) {
        rememberActiveRun(sourceId, e.jobId);
        shouldClearActiveRun = false;
        setMessage(`仍在后台运行（job_id=${e.jobId}，status=${e.lastStatus}）`);
        return;
      }
      if (e instanceof JobCancelledError) {
        shouldClearActiveRun = true;
        setMessage(`运行已取消（job_id=${e.jobId}）`);
        return;
      }
      if (e instanceof JobFailedError) {
        shouldClearActiveRun = true;
        setMessage(`执行失败：${e.errorMessage}（job_id=${e.jobId}）`);
        return;
      }
      shouldClearActiveRun = true;
      const msg = e instanceof Error ? e.message : "执行源失败，请查看后端日志";
      setMessage(msg);
    } finally {
      stopActing(sourceId);
      if (shouldClearActiveRun) clearActiveRun(sourceId);
    }
  }

  async function handleCancelSourceRun(sourceId: string, jobId: string) {
    setCancellingJobIds((prev) => new Set(prev).add(jobId));
    try {
      const result = await cancelJob(jobId);
      if (result.status === "cancelled") {
        clearActiveRun(sourceId);
        setMessage(`运行已取消（job_id=${jobId}）`);
        await load();
        setSourceRefreshKey((prev) => prev + 1);
        return;
      }

      setMessage(`已请求停止，等待任务收尾（job_id=${jobId}）`);
      const job = await waitForJob(jobId, 120_000, 1_000);
      if (job.status === "cancelled") {
        clearActiveRun(sourceId);
        setMessage(`运行已取消（job_id=${jobId}）`);
        await load();
        setSourceRefreshKey((prev) => prev + 1);
        return;
      }

      assertJobSucceeded(job);
      clearActiveRun(sourceId);
      setMessage(`停止请求未生效，任务已完成（job_id=${jobId}）`);
      await load();
      setSourceRefreshKey((prev) => prev + 1);
    } catch (e: unknown) {
      if (e instanceof JobCancelledError) {
        clearActiveRun(sourceId);
        setMessage(`运行已取消（job_id=${e.jobId}）`);
        return;
      }
      if (e instanceof JobTimeoutError) {
        setMessage(`已请求停止，但任务仍在后台收尾（job_id=${e.jobId}，status=${e.lastStatus}）`);
        return;
      }
      if (e instanceof JobFailedError) {
        clearActiveRun(sourceId);
        setMessage(`任务在取消请求后失败：${e.errorMessage}（job_id=${e.jobId}）`);
        return;
      }
      const msg = e instanceof Error ? e.message : `取消失败（job_id=${jobId}）`;
      setMessage(msg);
    } finally {
      setCancellingJobIds((prev) => {
        const next = new Set(prev);
        next.delete(jobId);
        return next;
      });
    }
  }

  function handleSelectSource(source: SourceRecord) {
    setSelectedSource(source);
  }

  return (
    <div className="page-content">
      <div className="feed-page-header">
        <h2>订阅源管理</h2>
        <div className="feed-page-actions">
          <button
            onClick={handleImportOPML}
            disabled={importingOPML}
            className="action-btn"
            title="从 OPML 文件导入订阅源"
          >
            {importingOPML ? "导入中..." : "导入 OPML"}
          </button>
          <button
            onClick={handleSyncLocalConfig}
            disabled={syncingConfig}
            className="action-btn"
            title="从本地 SailorRSSConfig.json 同步"
          >
            {syncingConfig ? "同步中..." : "同步本地配置"}
          </button>
          <button
            onClick={() => setShowAddSource(!showAddSource)}
            className={`add-source-btn ${showAddSource ? "active" : ""}`}
            title="手动添加源"
          >
            +
          </button>
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

      {showAddSource && (
        <div className="feed-page-add-form">
          <div className="add-source-form">
            <div className="source-type-selector">
              <label>源类型：</label>
              <select value={newSourceType} onChange={(e) => setNewSourceType(e.target.value)}>
                <option value="rss">RSS 订阅</option>
                <option value="atom">Atom 订阅</option>
                <option value="jsonfeed">JSON Feed</option>
                <option value="academic_api">学术 API (arXiv)</option>
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
                placeholder={
                  newSourceType === "opml" || newSourceType === "jsonl" || newSourceType === "manual_file"
                    ? "文件路径"
                    : "URL *"
                }
                className="source-endpoint-input"
              />
            </div>

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
        </div>
      )}

      {sourceStatus && (
        <div className="source-status-bar">
          <span className="status-item">
            🗂 订阅源: {sourceStatus.total} 个 ({sourceStatus.enabled} 启用
            {sourceStatus.errored > 0 && `, ${sourceStatus.errored} 异常`})
          </span>
        </div>
      )}

      <div className="feed-page-layout">
        <div className="feed-page-left">
          <SourceList
            sources={sources}
            selectedId={selectedSource ? selectedSource.source_id : null}
            onSelect={handleSelectSource}
          />
        </div>
        <div className="feed-page-right">
          <SourceDetail
            source={selectedSource}
            onRun={handleRunSource}
            onCancelRun={selectedSource ? (jobId) => handleCancelSourceRun(selectedSource.source_id, jobId) : undefined}
            onToggle={handleToggleSource}
            onDelete={handleDeleteSource}
            isActing={selectedSource ? actingSourceIds.has(selectedSource.source_id) : false}
            activeJobId={selectedSource ? activeRunJobs[selectedSource.source_id] ?? null : null}
            isCancelling={selectedSource ? Boolean(activeRunJobs[selectedSource.source_id] && cancellingJobIds.has(activeRunJobs[selectedSource.source_id])) : false}
            refreshKey={sourceRefreshKey}
          />
        </div>
      </div>
    </div>
  );
}
