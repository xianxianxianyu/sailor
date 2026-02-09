import { useEffect, useState } from "react";

import { getResourceAnalysis } from "../api";
import type { ResourceAnalysis } from "../types";

type Props = {
  resourceId: string;
};

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = (value / 10) * 100;
  return (
    <div className="score-bar">
      <span className="score-label">{label}</span>
      <div className="score-track">
        <div className="score-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="score-value">{value}</span>
    </div>
  );
}

export default function AnalysisPanel({ resourceId }: Props) {
  const [analysis, setAnalysis] = useState<ResourceAnalysis | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getResourceAnalysis(resourceId)
      .then(setAnalysis)
      .catch(() => setAnalysis(null))
      .finally(() => setLoading(false));
  }, [resourceId]);

  if (loading) {
    return <div className="analysis-panel analysis-loading">Loading analysis...</div>;
  }

  if (!analysis) {
    return <div className="analysis-panel analysis-empty">No analysis available.</div>;
  }

  const statusClass = `analysis-status-${analysis.status}`;

  return (
    <div className="analysis-panel">
      <h4>
        AI Analysis <span className={`analysis-badge ${statusClass}`}>{analysis.status}</span>
      </h4>

      {analysis.status === "completed" && (
        <>
          <div className="analysis-section">
            <h5>Summary</h5>
            <p>{analysis.summary}</p>
          </div>

          <div className="analysis-section">
            <h5>Topics</h5>
            <div className="topic-row">
              {analysis.topics.map((t) => (
                <span key={t} className="topic-chip">{t}</span>
              ))}
            </div>
          </div>

          <div className="analysis-section">
            <h5>Scores</h5>
            <ScoreBar label="Depth" value={analysis.scores.depth} />
            <ScoreBar label="Utility" value={analysis.scores.utility} />
            <ScoreBar label="Novelty" value={analysis.scores.novelty} />
          </div>

          {analysis.kb_recommendations.length > 0 && (
            <div className="analysis-section">
              <h5>KB Recommendations</h5>
              <ul className="kb-rec-list">
                {analysis.kb_recommendations.map((rec, i) => (
                  <li key={i}>
                    <strong>{rec.kb_id}</strong> ({Math.round(rec.confidence * 100)}%)
                    <span>{rec.reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="analysis-section">
            <h5>Insights</h5>
            {analysis.insights.core_arguments?.length > 0 && (
              <div>
                <h6>Core Arguments</h6>
                <ul>{analysis.insights.core_arguments.map((a, i) => <li key={i}>{a}</li>)}</ul>
              </div>
            )}
            {analysis.insights.tech_points?.length > 0 && (
              <div>
                <h6>Tech Points</h6>
                <ul>{analysis.insights.tech_points.map((t, i) => <li key={i}>{t}</li>)}</ul>
              </div>
            )}
            {analysis.insights.practices?.length > 0 && (
              <div>
                <h6>Practices</h6>
                <ul>{analysis.insights.practices.map((p, i) => <li key={i}>{p}</li>)}</ul>
              </div>
            )}
          </div>
        </>
      )}

      {analysis.status === "failed" && analysis.error_message && (
        <p className="analysis-error">{analysis.error_message}</p>
      )}
    </div>
  );
}
