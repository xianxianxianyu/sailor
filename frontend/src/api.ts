import type {
  AnalysisStatus,
  Board,
  BoardSnapshot,
  BoardSnapshotItem,
  CancelJobOut,
  ChannelHealth,
  ChannelInfo,
  CompareSummary,
  Follow,
  IssueSnapshot,
  JobOut,
  KBItemResource,
  KBReport,
  KGEdge,
  KGGraph,
  KGNodeDetail,
  KnowledgeBase,
  LLMSettings,
  MainFlowTask,
  ResearchProgram,
  Resource,
  ResourceAnalysis,
  RunSourceOut,
  SearchResponse,
  SnifferPack,
  SourceRecord,
  SourceResource,
  SourceRun,
  SourceStatus,
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
    let detail = "";
    try {
      const err = (await response.json()) as { detail?: unknown };
      if (typeof err?.detail === "string") detail = err.detail;
      else if (err?.detail !== undefined) detail = JSON.stringify(err.detail);
      else detail = JSON.stringify(err);
    } catch {
      // ignore body parse errors
    }
    throw new Error(detail ? `Request failed: ${response.status}: ${detail}` : `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// --- Job 状态错误类 ---

export class JobTimeoutError extends Error {
  jobId: string;
  lastStatus: string;

  constructor(jobId: string, lastStatus: string) {
    super(`Job ${jobId} timed out (last status: ${lastStatus})`);
    this.name = "JobTimeoutError";
    this.jobId = jobId;
    this.lastStatus = lastStatus;
  }
}

export class JobFailedError extends Error {
  jobId: string;
  errorMessage: string;

  constructor(jobId: string, errorMessage: string) {
    super(`Job ${jobId} failed: ${errorMessage}`);
    this.name = "JobFailedError";
    this.jobId = jobId;
    this.errorMessage = errorMessage;
  }
}

export class JobCancelledError extends Error {
  jobId: string;

  constructor(jobId: string) {
    super(`Job ${jobId} was cancelled`);
    this.name = "JobCancelledError";
    this.jobId = jobId;
  }
}

function isTerminalJobStatus(status: string): boolean {
  return status === "succeeded" || status === "failed" || status === "cancelled";
}

export function assertJobSucceeded(job: JobOut): void {
  if (job.status === "succeeded") return;
  if (job.status === "cancelled") throw new JobCancelledError(job.job_id);
  if (job.status === "failed") throw new JobFailedError(job.job_id, job.error_message ?? "Job failed");
  throw new JobTimeoutError(job.job_id, job.status);
}

export function getJob(jobId: string): Promise<JobOut> {
  return requestJson(`/jobs/${jobId}`);
}

export function cancelJob(jobId: string): Promise<CancelJobOut> {
  return requestJson(`/jobs/${jobId}/cancel`, { method: "POST" });
}

export async function waitForJob(jobId: string, timeoutMs = 120_000, pollIntervalMs = 1_000): Promise<JobOut> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const job = await getJob(jobId);
    if (isTerminalJobStatus(job.status)) {
      return job;
    }
    await sleep(pollIntervalMs);
  }
  const lastJob = await getJob(jobId);
  if (isTerminalJobStatus(lastJob.status)) {
    return lastJob;
  }
  throw new JobTimeoutError(jobId, lastJob.status);
}

export function getResources(topic?: string): Promise<Resource[]> {
  const suffix = topic ? `?status=inbox&topic=${encodeURIComponent(topic)}` : "?status=inbox";
  return requestJson(`/resources${suffix}`);
}

export function getKnowledgeBases(): Promise<KnowledgeBase[]> {
  return requestJson("/knowledge-bases");
}

export type AddToKnowledgeBaseOut = {
  kb_id: string;
  resource_id: string;
  added_at: string;
  kg_job_id?: string | null;
};

export function addToKnowledgeBase(kbId: string, resourceId: string): Promise<AddToKnowledgeBaseOut> {
  return requestJson(`/knowledge-bases/${kbId}/items`, {
    method: "POST",
    body: JSON.stringify({ resource_id: resourceId }),
  });
}

export function getResourceKnowledgeBases(resourceId: string): Promise<KnowledgeBase[]> {
  return requestJson(`/resources/${resourceId}/knowledge-bases`);
}

export function getMainFlowTasks(): Promise<MainFlowTask[]> {
  return requestJson("/tasks/main-flow");
}

// --- 分析 API ---

export function getResourceAnalysis(resourceId: string): Promise<ResourceAnalysis> {
  return requestJson(`/resources/${resourceId}/analysis`);
}

export function getAnalysisStatus(): Promise<AnalysisStatus> {
  return requestJson("/analyses/status");
}

// --- KB 报告 API ---

export async function generateKBReports(kbId: string, reportTypes?: string[]): Promise<KBReport[]> {
  const response = await fetch(`${API_BASE}/knowledge-bases/${kbId}/reports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(reportTypes ? { report_types: reportTypes } : {}),
  });
  if (!response.ok) {
    let detail = "";
    try {
      const err = (await response.json()) as { detail?: unknown };
      if (typeof err?.detail === "string") detail = err.detail;
      else if (err?.detail !== undefined) detail = JSON.stringify(err.detail);
      else detail = JSON.stringify(err);
    } catch {
      // ignore
    }
    throw new Error(detail ? `Request failed: ${response.status}: ${detail}` : `Request failed: ${response.status}`);
  }

  const data = (await response.json()) as unknown;
  if (Array.isArray(data)) {
    return data as KBReport[];
  }

  const jobId = (data as { job_id?: string } | null)?.job_id;
  if (!jobId) {
    throw new Error("Unexpected response from KB report generation");
  }

  const job = await waitForJob(jobId, 300_000, 1_000);
  assertJobSucceeded(job);

  let reportIds: string[] = [];
  try {
    const output = JSON.parse(job.output_json ?? "{}") as { report_ids?: string[] };
    reportIds = output.report_ids ?? [];
  } catch {
    // ignore
  }

  const all = await getKBReports(kbId);
  if (!reportIds.length) {
    return all;
  }

  const byId = new Map(all.map((r) => [r.report_id, r]));
  return reportIds.map((id) => byId.get(id)).filter(Boolean) as KBReport[];
}

export function getKBReports(kbId: string): Promise<KBReport[]> {
  return requestJson(`/knowledge-bases/${kbId}/reports`);
}

export function getLatestKBReports(kbId: string): Promise<KBReport[]> {
  return requestJson(`/knowledge-bases/${kbId}/reports/latest`);
}

// --- Sources API ---

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

export function importLocalSources(configFile?: string): Promise<{ imported: number; total_parsed: number }> {
  return requestJson("/sources/import-local", {
    method: "POST",
    body: JSON.stringify(configFile ? { config_file: configFile } : {}),
  });
}

export function importOpmlToSources(opmlFile?: string): Promise<{ imported: number; total_parsed: number }> {
  return requestJson("/sources/import-opml", {
    method: "POST",
    body: JSON.stringify(opmlFile ? { opml_file: opmlFile } : {}),
  });
}

export function runSource(
  sourceId: string,
  options?: { wait?: boolean; timeoutSec?: number }
): Promise<RunSourceOut> {
  const params = new URLSearchParams();
  if (options?.wait) params.set("wait", "true");
  if (options?.timeoutSec !== undefined) params.set("timeout", String(options.timeoutSec));
  const suffix = params.toString();
  return requestJson(`/sources/${sourceId}/run${suffix ? `?${suffix}` : ""}`, { method: "POST" });
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

export async function analyzeResource(resourceId: string): Promise<ResourceAnalysis> {
  const response = await fetch(`${API_BASE}/resources/${resourceId}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    let detail = "";
    try {
      const err = (await response.json()) as { detail?: unknown };
      if (typeof err?.detail === "string") detail = err.detail;
      else if (err?.detail !== undefined) detail = JSON.stringify(err.detail);
      else detail = JSON.stringify(err);
    } catch {
      // ignore
    }
    throw new Error(detail ? `Request failed: ${response.status}: ${detail}` : `Request failed: ${response.status}`);
  }

  const data = (await response.json()) as unknown;
  if ((data as { resource_id?: string } | null)?.resource_id) {
    return data as ResourceAnalysis;
  }

  const jobId = (data as { job_id?: string } | null)?.job_id;
  if (!jobId) {
    throw new Error("Unexpected response from analyze");
  }

  const job = await waitForJob(jobId, 180_000, 1_000);
  assertJobSucceeded(job);

  return getResourceAnalysis(resourceId);
}

// --- 资源嗅探 API ---

export function snifferSearch(payload: {
  keyword: string;
  channels?: string[];
  time_range?: string;
  sort_by?: string;
  max_results_per_channel?: number;
}): Promise<SearchResponse> {
  return (async () => {
    const data = await requestJson<SearchResponse>("/sniffer/search", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (!data.job_id || !data.status || data.status === "succeeded") {
      return data;
    }

    if (data.status === "failed") {
      throw new JobFailedError(data.job_id, data.error_message ?? "Search failed");
    }
    if (data.status === "cancelled") {
      throw new JobCancelledError(data.job_id);
    }

    const job = await waitForJob(data.job_id, 300_000, 2_000);
    assertJobSucceeded(job);
    return requestJson<SearchResponse>(`/sniffer/jobs/${data.job_id}`);
  })();
}

export function getSnifferChannels(): Promise<ChannelInfo[]> {
  return requestJson("/sniffer/channels");
}

export function getSnifferPacks(): Promise<SnifferPack[]> {
  return requestJson("/sniffer/packs");
}

export function createSnifferPack(payload: {
  name: string;
  query: {
    keyword: string;
    channels?: string[];
    time_range?: string;
    sort_by?: string;
    max_results_per_channel?: number;
  };
  description?: string;
}): Promise<SnifferPack> {
  return requestJson("/sniffer/packs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteSnifferPack(packId: string): Promise<void> {
  return requestJson(`/sniffer/packs/${packId}`, { method: "DELETE" }).then(() => undefined);
}

export function runSnifferPack(packId: string): Promise<SearchResponse> {
  return requestJson<SearchResponse>(`/sniffer/packs/${packId}/run`, { method: "POST" }).then(async (data) => {
    if (!data.job_id || !data.status || data.status === "succeeded") {
      return data;
    }
    if (data.status === "failed") {
      throw new JobFailedError(data.job_id, data.error_message ?? "Pack run failed");
    }
    if (data.status === "cancelled") {
      throw new JobCancelledError(data.job_id);
    }

    const job = await waitForJob(data.job_id, 300_000, 2_000);
    assertJobSucceeded(job);
    return requestJson<SearchResponse>(`/sniffer/jobs/${data.job_id}`);
  });
}

// --- P1: 深度分析 / 对比 / 操作 ---

export async function deepAnalyze(resultId: string): Promise<ResourceAnalysis> {
  const response = await fetch(`${API_BASE}/sniffer/results/${resultId}/deep-analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    let detail = "";
    try {
      const err = (await response.json()) as { detail?: unknown };
      if (typeof err?.detail === "string") detail = err.detail;
      else if (err?.detail !== undefined) detail = JSON.stringify(err.detail);
      else detail = JSON.stringify(err);
    } catch {
      // ignore
    }
    throw new Error(detail ? `Request failed: ${response.status}: ${detail}` : `Request failed: ${response.status}`);
  }

  const data = (await response.json()) as unknown;
  if ((data as { resource_id?: string } | null)?.resource_id) {
    return data as ResourceAnalysis;
  }

  const jobId = (data as { job_id?: string } | null)?.job_id;
  if (!jobId) {
    throw new Error("Unexpected response from deep-analyze");
  }

  const job = await waitForJob(jobId, 180_000, 1_000);
  assertJobSucceeded(job);

  let resourceId = "";
  try {
    const output = JSON.parse(job.output_json ?? "{}") as { resource_id?: string };
    resourceId = output.resource_id ?? "";
  } catch {
    // ignore
  }

  if (!resourceId) {
    throw new Error(`Missing resource_id in deep-analyze job output (job_id=${jobId})`);
  }
  return getResourceAnalysis(resourceId);
}

function isValidCompareSummary(data: unknown): data is CompareSummary {
  if (typeof data !== "object" || data === null) return false;
  const obj = data as Record<string, unknown>;
  if (!Array.isArray(obj.dimensions)) return false;
  if (typeof obj.verdict !== "string") return false;
  if (typeof obj.model !== "string") return false;
  return true;
}

export async function compareResults(resultIds: string[]): Promise<CompareSummary> {
  const response = await fetch(`${API_BASE}/sniffer/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result_ids: resultIds }),
  });
  if (!response.ok) {
    let detail = "";
    try {
      const err = (await response.json()) as { detail?: unknown };
      if (typeof err?.detail === "string") detail = err.detail;
      else if (err?.detail !== undefined) detail = JSON.stringify(err.detail);
      else detail = JSON.stringify(err);
    } catch {
      // ignore
    }
    throw new Error(detail ? `Request failed: ${response.status}: ${detail}` : `Request failed: ${response.status}`);
  }

  const data = (await response.json()) as unknown;
  if (Array.isArray((data as CompareSummary | null)?.dimensions)) {
    return data as CompareSummary;
  }

  const jobId = (data as { job_id?: string } | null)?.job_id;
  if (!jobId) {
    throw new Error("Unexpected response from compare");
  }

  const job = await waitForJob(jobId, 180_000, 1_000);
  assertJobSucceeded(job);

  let parsed: unknown;
  try {
    parsed = JSON.parse(job.output_json ?? "{}");
  } catch {
    throw new Error(`Failed to parse compare job output (job_id=${jobId})`);
  }
  if (!isValidCompareSummary(parsed)) {
    throw new Error(`Invalid compare job output (job_id=${jobId})`);
  }
  return parsed;
}

export async function saveToKB(resultId: string, kbId: string): Promise<{ saved: boolean; resource_id: string }> {
  const response = await fetch(`${API_BASE}/sniffer/results/${resultId}/save-to-kb?wait=true&timeout=30`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kb_id: kbId }),
  });
  if (!response.ok) {
    let detail = "";
    try {
      const err = (await response.json()) as { detail?: unknown };
      if (typeof err?.detail === "string") detail = err.detail;
      else if (err?.detail !== undefined) detail = JSON.stringify(err.detail);
      else detail = JSON.stringify(err);
    } catch {
      // ignore
    }
    throw new Error(detail ? `Request failed: ${response.status}: ${detail}` : `Request failed: ${response.status}`);
  }

  const data = (await response.json()) as unknown;
  const saved = (data as { saved?: boolean } | null)?.saved;
  if (saved) {
    return data as { saved: boolean; resource_id: string };
  }

  const jobId = (data as { job_id?: string } | null)?.job_id;
  if (!jobId) {
    throw new Error("Unexpected response from save-to-kb");
  }

  const job = await waitForJob(jobId, 120_000, 1_000);
  assertJobSucceeded(job);

  try {
    const output = JSON.parse(job.output_json ?? "{}") as { resource_id?: string };
    const resourceId = output.resource_id;
    if (!resourceId) {
      throw new Error("Missing resource_id in job output");
    }
    return { saved: true, resource_id: resourceId };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Failed to parse save-to-kb job output";
    throw new Error(msg);
  }
}

export async function convertToSource(resultId: string, name?: string): Promise<{ converted: boolean; source_id: string }> {
  const response = await fetch(`${API_BASE}/sniffer/results/${resultId}/convert-source?wait=true&timeout=30`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    let detail = "";
    try {
      const err = (await response.json()) as { detail?: unknown };
      if (typeof err?.detail === "string") detail = err.detail;
      else if (err?.detail !== undefined) detail = JSON.stringify(err.detail);
      else detail = JSON.stringify(err);
    } catch {
      // ignore
    }
    throw new Error(detail ? `Request failed: ${response.status}: ${detail}` : `Request failed: ${response.status}`);
  }

  const data = (await response.json()) as unknown;
  const converted = (data as { converted?: boolean } | null)?.converted;
  if (converted) {
    return data as { converted: boolean; source_id: string };
  }

  const jobId = (data as { job_id?: string } | null)?.job_id;
  if (!jobId) {
    throw new Error("Unexpected response from convert-source");
  }

  const job = await waitForJob(jobId, 120_000, 1_000);
  assertJobSucceeded(job);

  try {
    const output = JSON.parse(job.output_json ?? "{}") as { source_id?: string };
    const sourceId = output.source_id;
    if (!sourceId) {
      throw new Error("Missing source_id in job output");
    }
    return { converted: true, source_id: sourceId };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Failed to parse convert-source job output";
    throw new Error(msg);
  }
}

export function importSnifferPack(payload: {
  name: string;
  query: { keyword: string; channels?: string[]; time_range?: string; sort_by?: string; max_results_per_channel?: number };
  description?: string;
  schedule_cron?: string;
}): Promise<SnifferPack> {
  return requestJson("/sniffer/packs/import", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function exportSnifferPack(packId: string): Promise<Record<string, unknown>> {
  return requestJson(`/sniffer/packs/${packId}/export`);
}

export function updatePackSchedule(packId: string, scheduleCron: string | null): Promise<SnifferPack> {
  return requestJson(`/sniffer/packs/${packId}/schedule`, {
    method: "PATCH",
    body: JSON.stringify({ schedule_cron: scheduleCron }),
  });
}

export function getChannelHealth(): Promise<ChannelHealth[]> {
  return requestJson("/sniffer/channels/health");
}

// --- Follow API ---

export function listFollows(enabled?: boolean): Promise<Follow[]> {
  const suffix = enabled !== undefined ? `?enabled=${enabled}` : "";
  return requestJson(`/follows${suffix}`);
}

export function createFollow(data: {
  name: string;
  description?: string;
  board_ids: string[];
  research_program_ids: string[];
  window_policy: string;
  enabled: boolean;
  schedule_minutes?: number;
}): Promise<Follow> {
  return requestJson("/follows", { method: "POST", body: JSON.stringify(data) });
}

export function updateFollow(id: string, data: Partial<Follow>): Promise<Follow> {
  return requestJson(`/follows/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function deleteFollow(id: string): Promise<void> {
  return requestJson(`/follows/${id}`, { method: "DELETE" }).then(() => undefined);
}

export function triggerFollowRun(id: string): Promise<{ job_id: string; follow_id: string; status: string; error_message?: string }> {
  return requestJson(`/follows/${id}/run`, { method: "POST" });
}

export function getLatestIssue(id: string): Promise<IssueSnapshot | null> {
  return requestJson<IssueSnapshot | null>(`/follows/${id}/issues/latest`).catch(() => null);
}

export function listIssues(id: string, limit = 5): Promise<IssueSnapshot[]> {
  return requestJson(`/follows/${id}/issues?limit=${limit}`);
}

// --- Board API ---

export function listBoards(enabled?: boolean): Promise<Board[]> {
  const suffix = enabled !== undefined ? `?enabled=${enabled}` : "";
  return requestJson(`/boards${suffix}`);
}

export function createBoard(data: {
  provider: string;
  kind: string;
  name: string;
  enabled: boolean;
}): Promise<Board> {
  return requestJson("/boards", { method: "POST", body: JSON.stringify(data) });
}

export function updateBoard(id: string, data: Partial<Board>): Promise<Board> {
  return requestJson(`/boards/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function deleteBoard(id: string): Promise<void> {
  return requestJson(`/boards/${id}`, { method: "DELETE" }).then(() => undefined);
}

export function triggerBoardSnapshot(id: string): Promise<{ job_id: string; snapshot_id: string; status: string; error_message?: string }> {
  return requestJson(`/boards/${id}/snapshot`, { method: "POST" });
}

export function getLatestSnapshot(id: string): Promise<BoardSnapshot | null> {
  return requestJson<BoardSnapshot | null>(`/boards/${id}/snapshots/latest`).catch(() => null);
}

export function listSnapshotItems(snapshotId: string, limit = 50): Promise<BoardSnapshotItem[]> {
  return requestJson(`/boards/snapshots/${snapshotId}/items?limit=${limit}`);
}

// --- Research Program API ---

export function listResearchPrograms(enabled?: boolean): Promise<ResearchProgram[]> {
  const suffix = enabled !== undefined ? `?enabled=${enabled}` : "";
  return requestJson(`/research-programs${suffix}`);
}

export function createResearchProgram(data: {
  name: string;
  description?: string;
  enabled: boolean;
}): Promise<ResearchProgram> {
  return requestJson("/research-programs", { method: "POST", body: JSON.stringify(data) });
}

export function updateResearchProgram(id: string, data: Partial<ResearchProgram>): Promise<ResearchProgram> {
  return requestJson(`/research-programs/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function deleteResearchProgram(id: string): Promise<void> {
  return requestJson(`/research-programs/${id}`, { method: "DELETE" }).then(() => undefined);
}

export function getResearchProgram(programId: string): Promise<ResearchProgram> {
  return requestJson(`/research-programs/${programId}`);
}

export function getBoardSnapshots(
  boardId: string,
  limit = 10
): Promise<BoardSnapshot[]> {
  return requestJson(`/boards/${boardId}/snapshots?limit=${limit}`);
}

// --- KG Graph API ---

export function getKBGraph(
  kbId: string,
  params?: {
    mode?: "full" | "local";
    start_node_id?: string;
    depth?: number;
    limit?: number;
  }
): Promise<KGGraph> {
  const queryParams = new URLSearchParams();
  if (params?.mode) queryParams.set("mode", params.mode);
  if (params?.start_node_id) queryParams.set("start_node_id", params.start_node_id);
  if (params?.depth) queryParams.set("depth", params.depth.toString());
  if (params?.limit) queryParams.set("limit", params.limit.toString());

  const query = queryParams.toString();
  return requestJson<KGGraph>(
    `/knowledge-bases/${kbId}/graph${query ? `?${query}` : ""}`
  );
}

export function getKBGraphNode(
  kbId: string,
  nodeId: string,
  page: number = 1,
  pageSize: number = 50
): Promise<KGNodeDetail> {
  return requestJson<KGNodeDetail>(
    `/knowledge-bases/${kbId}/graph/nodes/${nodeId}?page=${page}&page_size=${pageSize}`
  );
}

export function createKBGraphEdge(
  kbId: string,
  payload: { node_a_id: string; node_b_id: string; reason: string; reason_type?: string }
): Promise<KGEdge> {
  return requestJson(`/knowledge-bases/${kbId}/graph/edges`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteKBGraphEdge(
  kbId: string,
  nodeAId: string,
  nodeBId: string
): Promise<{ deleted: boolean }> {
  return requestJson(`/knowledge-bases/${kbId}/graph/edges/${nodeAId}/${nodeBId}`, {
    method: "DELETE",
  });
}

export function freezeKBGraphEdge(
  kbId: string,
  nodeAId: string,
  nodeBId: string
): Promise<{ frozen: boolean }> {
  return requestJson(`/knowledge-bases/${kbId}/graph/edges/${nodeAId}/${nodeBId}/freeze`, {
    method: "POST",
  });
}

export function unfreezeKBGraphEdge(
  kbId: string,
  nodeAId: string,
  nodeBId: string
): Promise<{ frozen: boolean }> {
  return requestJson(`/knowledge-bases/${kbId}/graph/edges/${nodeAId}/${nodeBId}/unfreeze`, {
    method: "POST",
  });
}

export function relinkKBGraphNode(
  kbId: string,
  nodeId: string
): Promise<{ job_id: string; status: string }> {
  return requestJson(`/knowledge-bases/${kbId}/graph/nodes/${nodeId}/relink`, {
    method: "POST",
  });
}

export function getKBGraphHistory(
  kbId: string,
  limit: number = 50
): Promise<{ jobs: Array<{
  job_id: string;
  job_type: string;
  status: string;
  node_id: string;
  created_at: string | null;
  finished_at: string | null;
  output: string | null;
}> }> {
  return requestJson(`/knowledge-bases/${kbId}/graph/history?limit=${limit}`);
}

