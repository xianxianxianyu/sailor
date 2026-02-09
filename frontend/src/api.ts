import type { KnowledgeBase, MainFlowTask, Resource } from "./types";

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
