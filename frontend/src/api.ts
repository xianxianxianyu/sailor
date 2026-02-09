import type { AnalysisStatus, KBReport, KnowledgeBase, MainFlowTask, Resource, ResourceAnalysis, RSSFeed } from "./types";

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
