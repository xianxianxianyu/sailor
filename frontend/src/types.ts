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

export type RSSFeed = {
  feed_id: string;
  name: string;
  xml_url: string;
  html_url: string | null;
  enabled: boolean;
  last_fetched_at: string | null;
  error_count: number;
  last_error: string | null;
};

// --- Tag 类型 ---

export type UserTag = {
  tag_id: string;
  name: string;
  color: string;
  weight: number;
  created_at: string | null;
};

// --- Trending 类型 ---

export type TrendingItem = {
  resource_id: string;
  title: string;
  original_url: string;
  summary: string;
  tags: string[];
  source: string;
};

export type TrendingGroup = {
  tag_name: string;
  tag_color: string;
  items: TrendingItem[];
};

export type TrendingReport = {
  groups: TrendingGroup[];
  total_resources: number;
  total_tags: number;
};

export type PipelineResult = {
  collected: number;
  processed: number;
  tagged: number;
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
