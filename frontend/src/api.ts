import type {
  AnalysisStatus,
  KBItemResource,
  KBReport,
  KnowledgeBase,
  LLMSettings,
  MainFlowTask,
  PipelineResult,
  Resource,
  ResourceAnalysis,
  RSSFeed,
  SourceRecord,
  SourceResource,
  SourceRun,
  SourceStatus,
  TrendingReport,
  UserTag,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export function runIngestion(): Promise<{ collected_count: number; processed_count: number }> {
  return requestJson("/tasks/run-ingestion", { method: "POST" });
}

export function getResources(topic?: string): Promise<Resource[]> {
  const suffix = topic ? `?status=inbox&topic=${encodeURIComponent(topic)}` : "?status=inbox";
  return requestJson(`/resources${suffix}`);
}

export function getKnowledgeBases(): Promise<KnowledgeBase[]> {
  return requestJson("/knowledge-bases");
}

export function addToKnowledgeBase(kbId: string, resourceId: string): Promise<void> {
  return requestJson(`/knowledge-bases/${kbId}/items`, {
    method: "POST",
    body: JSON.stringify({ resource_id: resourceId }),
  }).then(() => undefined);
}

export function getResourceKnowledgeBases(resourceId: string): Promise<KnowledgeBase[]> {
  return requestJson(`/resources/${resourceId}/knowledge-bases`);
}

export function getMainFlowTasks(): Promise<MainFlowTask[]> {
  return requestJson("/tasks/main-flow");
}

// --- 分析 API ---

export function runAnalysis(resourceIds?: string[]): Promise<{ analyzed_count: number; failed_count: number }> {
  return requestJson("/tasks/run-analysis", {
    method: "POST",
    body: JSON.stringify(resourceIds ? { resource_ids: resourceIds } : {}),
  });
}

export function getResourceAnalysis(resourceId: string): Promise<ResourceAnalysis> {
  return requestJson(`/resources/${resourceId}/analysis`);
}

export function getAnalysisStatus(): Promise<AnalysisStatus> {
  return requestJson("/analyses/status");
}

// --- KB 报告 API ---

export function generateKBReports(kbId: string, reportTypes?: string[]): Promise<KBReport[]> {
  return requestJson(`/knowledge-bases/${kbId}/reports`, {
    method: "POST",
    body: JSON.stringify(reportTypes ? { report_types: reportTypes } : {}),
  });
}

export function getKBReports(kbId: string): Promise<KBReport[]> {
  return requestJson(`/knowledge-bases/${kbId}/reports`);
}

export function getLatestKBReports(kbId: string): Promise<KBReport[]> {
  return requestJson(`/knowledge-bases/${kbId}/reports/latest`);
}

// --- Feed 管理 API ---

export function getFeeds(): Promise<RSSFeed[]> {
  return requestJson("/feeds");
}

export function importOPML(opmlFile?: string): Promise<{ imported: number; total_parsed: number }> {
  return requestJson("/feeds/import-opml", {
    method: "POST",
    body: JSON.stringify(opmlFile ? { opml_file: opmlFile } : {}),
  });
}

export function addFeed(name: string, xmlUrl: string, htmlUrl?: string): Promise<RSSFeed> {
  return requestJson("/feeds", {
    method: "POST",
    body: JSON.stringify({ name, xml_url: xmlUrl, html_url: htmlUrl }),
  });
}

export function deleteFeed(feedId: string): Promise<void> {
  return requestJson(`/feeds/${feedId}`, { method: "DELETE" }).then(() => undefined);
}

export function toggleFeed(feedId: string, enabled: boolean): Promise<void> {
  return requestJson(`/feeds/${feedId}?enabled=${enabled}`, { method: "PATCH" }).then(() => undefined);
}

export function getSourceStatus(): Promise<{
  rss_total: number;
  rss_enabled: number;
  rss_errored: number;
  miniflux_configured: boolean;
  seed_file_exists: boolean;
}> {
  return requestJson("/feeds/source-status");
}

export function getSources(sourceType?: string, enabledOnly = false): Promise<SourceRecord[]> {
  const params = new URLSearchParams();
  if (sourceType) params.set("source_type", sourceType);
  if (enabledOnly) params.set("enabled_only", "true");
  const suffix = params.toString();
  return requestJson(`/sources${suffix ? `?${suffix}` : ""}`);
}

export function createSource(payload: {
  source_id?: string;
  source_type: string;
  name: string;
  endpoint?: string | null;
  config?: Record<string, unknown>;
  enabled?: boolean;
  schedule_minutes?: number;
}): Promise<SourceRecord> {
  return requestJson("/sources", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateSource(
  sourceId: string,
  payload: {
    name?: string;
    endpoint?: string | null;
    config?: Record<string, unknown>;
    enabled?: boolean;
    schedule_minutes?: number;
  }
): Promise<SourceRecord> {
  return requestJson(`/sources/${sourceId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteSource(sourceId: string): Promise<void> {
  return requestJson(`/sources/${sourceId}`, { method: "DELETE" }).then(() => undefined);
}

export function getUnifiedSourceStatus(): Promise<SourceStatus> {
  return requestJson("/sources/status");
}

export function importLocalSources(configFile?: string): Promise<{ imported: number; rss_synced: number; total_parsed: number }> {
  return requestJson("/sources/import-local", {
    method: "POST",
    body: JSON.stringify(configFile ? { config_file: configFile } : {}),
  });
}

export function runSource(sourceId: string): Promise<{ run_id: string; source_id: string; status: string; fetched_count: number; processed_count: number }> {
  return requestJson(`/sources/${sourceId}/run`, { method: "POST" });
}

export function runFeed(feedId: string): Promise<{ feed_id: string; status: string; fetched_count: number; processed_count: number }> {
  return requestJson(`/feeds/${feedId}/run`, { method: "POST" });
}

export function runSourcesByType(sourceType: string, enabledOnly = true): Promise<{
  source_type: string;
  total_sources: number;
  success_count: number;
  failed_count: number;
  total_fetched: number;
  total_processed: number;
}> {
  return requestJson(`/sources/run-by-type/${sourceType}?enabled_only=${enabledOnly}`, { method: "POST" });
}

export function getSourceRuns(sourceId: string, limit = 20): Promise<SourceRun[]> {
  return requestJson(`/sources/${sourceId}/runs?limit=${limit}`);
}

export function getSourceResources(sourceId: string, limit = 50, offset = 0): Promise<SourceResource[]> {
  return requestJson(`/sources/${sourceId}/resources?limit=${limit}&offset=${offset}`);
}

export function getFeedResources(feedId: string, limit = 50, offset = 0): Promise<SourceResource[]> {
  return requestJson(`/feeds/${feedId}/resources?limit=${limit}&offset=${offset}`);
}

// --- Tag API ---

export function getTags(): Promise<UserTag[]> {
  return requestJson("/tags");
}

export function createTag(name: string, color?: string): Promise<UserTag> {
  return requestJson("/tags", {
    method: "POST",
    body: JSON.stringify({ name, color: color ?? "#0f766e" }),
  });
}

export function deleteTag(tagId: string): Promise<void> {
  return requestJson(`/tags/${tagId}`, { method: "DELETE" }).then(() => undefined);
}

// --- Trending API ---

export function generateTrending(): Promise<TrendingReport> {
  return requestJson("/trending/generate", { method: "POST" });
}

export function getTrending(): Promise<TrendingReport> {
  return requestJson("/trending");
}

export function runFullPipeline(): Promise<PipelineResult> {
  return requestJson("/trending/pipeline", { method: "POST" });
}

// --- KB 增强 API ---

export function createKnowledgeBase(name: string, description?: string): Promise<KnowledgeBase> {
  return requestJson("/knowledge-bases", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

export function deleteKnowledgeBase(kbId: string): Promise<void> {
  return requestJson(`/knowledge-bases/${kbId}`, { method: "DELETE" }).then(() => undefined);
}

export function getKBItems(kbId: string): Promise<KBItemResource[]> {
  return requestJson(`/knowledge-bases/${kbId}/items`);
}

export function removeKBItem(kbId: string, resourceId: string): Promise<void> {
  return requestJson(`/knowledge-bases/${kbId}/items/${resourceId}`, { method: "DELETE" }).then(() => undefined);
}

// --- 日志 API ---

export interface LogEntry {
  time: string;
  level: string;
  message: string;
}

export function getRecentLogs(limit = 50): Promise<LogEntry[]> {
  return requestJson(`/logs?limit=${limit}`);
}

export function createLogStream(): EventSource {
  return new EventSource(`${API_BASE}/logs/stream`);
}

// --- 抓取状态 API ---

export interface IngestionStatus {
  status: "idle" | "running" | "completed";
  last_run: string | null;
  new_count: number;
  updated_count: number;
  skipped_count: number;
}

export function getIngestionStatus(): Promise<IngestionStatus> {
  return requestJson("/tasks/ingestion-status");
}

// --- LLM 设置 API ---

export function getLLMSettings(): Promise<LLMSettings> {
  return requestJson("/settings/llm");
}

export function updateLLMSettings(payload: {
  provider: string;
  api_key?: string;
  base_url: string;
  model: string;
  temperature: number;
  max_tokens: number;
}): Promise<LLMSettings> {
  return requestJson("/settings/llm", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function testLLMConnection(): Promise<{ success: boolean; message: string }> {
  return requestJson("/settings/llm/test", { method: "POST" });
}

// --- 单条 LLM 分析 API ---

export function analyzeResource(resourceId: string): Promise<ResourceAnalysis> {
  return requestJson(`/resources/${resourceId}/analyze`, { method: "POST" });
}
