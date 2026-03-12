export type Resource = {
  resource_id: string;
  canonical_url: string;
  source: string;
  title: string;
  published_at: string | null;
  text: string;
  original_url: string;
  topics: string[];
  summary: string;
};

export type KnowledgeBase = {
  kb_id: string;
  name: string;
  description: string | null;
};

export type MainFlowTask = {
  task_id: string;
  task_type: string;
  title: string;
  description: string;
  resource_id: string;
  priority: string;
  status: string;
};

export type ResourceAnalysis = {
  resource_id: string;
  summary: string;
  topics: string[];
  scores: { depth: number; utility: number; novelty: number };
  kb_recommendations: { kb_id: string; confidence: number; reason: string }[];
  insights: { core_arguments: string[]; tech_points: string[]; practices: string[] };
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  status: "pending" | "completed" | "failed";
  error_message: string | null;
  created_at: string | null;
  completed_at: string | null;
};

export type AnalysisStatus = {
  total: number;
  pending: number;
  completed: number;
  failed: number;
};

export type KBReport = {
  report_id: string;
  kb_id: string;
  report_type: string;
  content: Record<string, unknown>;
  resource_count: number;
  model: string;
  status: string;
  created_at: string | null;
};

export type SourceRecord = {
  source_id: string;
  source_type: string;
  name: string;
  endpoint: string | null;
  config: Record<string, unknown>;
  enabled: boolean;
  schedule_minutes: number;
  last_run_at: string | null;
  error_count: number;
  last_error: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type SourceStatus = {
  total: number;
  enabled: number;
  errored: number;
  last_run_at: string | null;
};

export type SourceRun = {
  run_id: string;
  source_id: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  fetched_count: number;
  processed_count: number;
  error_message: string | null;
  metadata: Record<string, unknown>;
};

export type RunSourceOut = {
  job_id: string;
  run_id: string;
  source_id: string;
  status: string;
  fetched_count: number;
  processed_count: number;
  error_message: string | null;
};

export type SourceResource = {
  resource_id: string;
  canonical_url: string;
  source: string;
  title: string;
  published_at: string | null;
  text: string;
  original_url: string;
  topics: string[];
  summary: string;
  last_seen_at: string | null;
};

// --- Tag 类型 ---

export type UserTag = {
  tag_id: string;
  name: string;
  color: string;
  weight: number;
  created_at: string | null;
};

// --- KB Item 类型 ---

export type KBItemResource = {
  resource_id: string;
  title: string;
  original_url: string;
  summary: string;
  topics: string[];
  added_at: string;
};

// --- LLM 设置类型 ---

export type LLMSettings = {
  provider: string;
  api_key_set: boolean;
  api_key_preview: string;
  base_url: string;
  model: string;
  temperature: number;
  max_tokens: number;
};

// --- 资源嗅探类型 ---

export type SniffResult = {
  result_id: string;
  channel: string;
  title: string;
  url: string;
  snippet: string;
  author: string | null;
  published_at: string | null;
  media_type: string;
  metrics: Record<string, number>;
  query_keyword: string;
};

export type SniffQuery = {
  keyword: string;
  channels: string[];
  time_range: string;
  sort_by: string;
  max_results_per_channel: number;
};

export type SearchSummary = {
  total: number;
  keyword: string;
  channel_distribution: Record<string, number>;
  keyword_clusters: { word: string; count: number }[];
  time_distribution: Record<string, number>;
  top_by_engagement: { result_id: string; title: string; channel: string; engagement: number }[];
};

export type SearchResponse = {
  job_id?: string | null;
  status?: string | null;
  error_message?: string | null;
  results: SniffResult[];
  summary: SearchSummary;
};

// --- Jobs (V2 Provenance) ---

export type JobOut = {
  job_id: string;
  job_type: string;
  status: string;
  input_json: string;
  output_json: string | null;
  error_class: string | null;
  error_message: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  metadata: Record<string, unknown>;
};

export type CancelJobOut = {
  job_id: string;
  status: string;
  cancel_requested: boolean;
};

export type ChannelInfo = {
  channel_id: string;
  display_name: string;
  icon: string;
  tier: string;
  media_types: string[];
  status: string;
  message: string;
};

export type SnifferPack = {
  pack_id: string;
  name: string;
  query_json: string;
  description: string | null;
  schedule_cron: string | null;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string | null;
};

export type CompareSummary = {
  dimensions: { name: string; items: { title: string; score: number; comment: string }[] }[];
  verdict: string;
  model: string;
};

export type ChannelHealth = {
  channel_id: string;
  display_name: string;
  icon: string;
  tier: string;
  status: string;
  message: string;
  latency_ms: number | null;
};

// --- Follow 类型 ---

export interface Follow {
  follow_id: string;
  name: string;
  description?: string;
  board_ids: string[];
  research_program_ids: string[];
  window_policy: string;
  schedule_minutes?: number;
  enabled: boolean;
  last_run_at?: string;
  error_count: number;
  last_error?: string;
  created_at: string;
  updated_at: string;
}

export interface IssueItem {
  item_key: string;
  title?: string;
  url?: string;
  meta?: Record<string, unknown>;
}

export interface IssueSection {
  section_type: string;
  source_id: string;
  source_name?: string;
  new_items: IssueItem[];
  removed_items: IssueItem[];
  kept_items: IssueItem[];
}

export interface IssueSnapshot {
  issue_id: string;
  follow_id: string;
  window: { since?: string; until?: string };
  sections: IssueSection[];
  metadata: Record<string, unknown>;
  created_at: string;
}

// --- Board 类型 ---

export interface Board {
  board_id: string;
  provider: string;
  kind: string;
  name: string;
  config: Record<string, unknown>;
  enabled: boolean;
  last_run_at?: string;
  created_at: string;
  updated_at: string;
}

export interface BoardSnapshotItem {
  snapshot_id: string;
  item_key: string;
  source_order: number;
  title?: string;
  url?: string;
  meta?: Record<string, unknown>;
}

export interface BoardSnapshot {
  snapshot_id: string;
  board_id: string;
  captured_at: string;
  item_count: number;
}

// --- Research Program 类型 ---

export interface ResearchProgram {
  program_id: string;
  name: string;
  description: string;
  source_ids: string[];
  filters?: Record<string, unknown>;
  enabled: boolean;
  last_run_at?: string;
  created_at: string;
  updated_at: string;
}

// --- KG Graph 类型 ---

export type KGNode = {
  id: string;
  title: string;
  summary: string;
  url: string;
  topics_json: string;
  added_at: string;
};

export type KGEdge = {
  source: string;
  target: string;
  node_a_id: string;
  node_b_id: string;
  reason: string;
  reason_type: string | null;
  status: "active" | "deleted";
  frozen: number;
  created_by: string;
  created_at: string;
};

export type KGGraph = {
  nodes: KGNode[];
  edges: KGEdge[];
};

export type KGNeighbor = {
  node: KGNode;
  edge: KGEdge;
};

export type KGNodeDetail = {
  node: KGNode;
  neighbors: KGNeighbor[];
  total_neighbors?: number;
  page?: number;
  page_size?: number;
};
