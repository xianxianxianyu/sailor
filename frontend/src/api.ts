import type { AnalysisStatus, KBItemResource, KBReport, KnowledgeBase, MainFlowTask, PipelineResult, Resource, ResourceAnalysis, RSSFeed, TrendingReport, UserTag } from "./types";

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
