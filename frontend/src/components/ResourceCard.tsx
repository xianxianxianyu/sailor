import { useEffect, useState } from "react";

import { getResourceAnalysis } from "../api";
import type { Resource, ResourceAnalysis } from "../types";

type Props = {
  resource: Resource;
  archivedCount: number;
  onOpen: (resource: Resource) => void;
  onAdd: (resource: Resource) => void;
};

export default function ResourceCard({ resource, archivedCount, onOpen, onAdd }: Props) {
  const [analysis, setAnalysis] = useState<ResourceAnalysis | null>(null);

  useEffect(() => {
    getResourceAnalysis(resource.resource_id)
      .then(setAnalysis)
      .catch(() => setAnalysis(null));
  }, [resource.resource_id]);

  return (
    <article className="resource-card">
      <header>
        <button className="link-button" onClick={() => onOpen(resource)}>
          {resource.title}
        </button>
        <div className="card-badges">
          {analysis?.status === "completed" && analysis.scores && (
            <span className="score-badge">
              D:{analysis.scores.depth} U:{analysis.scores.utility} N:{analysis.scores.novelty}
            </span>
          )}
          <button className="plus-button" onClick={() => onAdd(resource)} aria-label="Add to knowledge base">
            +
          </button>
        </div>
      </header>
      <div className="topic-row">
        {resource.topics.map((topic) => (
          <span key={topic} className="topic-chip">
            {topic}
          </span>
        ))}
      </div>
      <p>{resource.summary}</p>
      <footer>
        <a href={resource.original_url} target="_blank" rel="noreferrer">
          Open source
        </a>
        <div className="card-footer-right">
          {analysis?.kb_recommendations && analysis.kb_recommendations.length > 0 && (
            <span className="kb-rec-flag">KB rec</span>
          )}
          {archivedCount > 0 ? <span className="archived-flag">Archived x{archivedCount}</span> : null}
        </div>
      </footer>
    </article>
  );
}
