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
