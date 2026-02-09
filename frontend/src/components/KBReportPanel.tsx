import { useEffect, useState } from "react";

import { generateKBReports, getLatestKBReports } from "../api";
import type { KBReport } from "../types";

type Props = {
  kbId: string;
};

export default function KBReportPanel({ kbId }: Props) {
  const [reports, setReports] = useState<KBReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    setLoading(true);
    getLatestKBReports(kbId)
      .then(setReports)
      .catch(() => setReports([]))
      .finally(() => setLoading(false));
  }, [kbId]);

  async function onGenerate() {
    setGenerating(true);
    try {
      const newReports = await generateKBReports(kbId);
      setReports(newReports);
    } finally {
      setGenerating(false);
    }
  }

  if (loading) {
    return <div className="kb-report-panel">Loading reports...</div>;
  }

  return (
    <div className="kb-report-panel">
      <div className="kb-report-header">
        <h4>KB Reports</h4>
        <button onClick={onGenerate} disabled={generating} className="generate-btn">
          {generating ? "Generating..." : "Generate Reports"}
        </button>
      </div>

      {reports.length === 0 ? (
        <div className="empty">No reports yet. Click "Generate Reports" to create.</div>
      ) : (
        <div className="kb-report-list">
          {reports.map((report) => (
            <ReportCard key={report.report_id} report={report} />
          ))}
        </div>
      )}
    </div>
  );
}

function ReportCard({ report }: { report: KBReport }) {
  const [expanded, setExpanded] = useState(false);
  const content = report.content as Record<string, unknown>;

  const typeLabels: Record<string, string> = {
    cluster: "Cluster Analysis",
    association: "Association Analysis",
    summary: "Knowledge Summary",
  };

  return (
    <div className="kb-report-card">
      <header onClick={() => setExpanded(!expanded)}>
        <strong>{typeLabels[report.report_type] || report.report_type}</strong>
        <span className={`analysis-badge analysis-status-${report.status}`}>{report.status}</span>
        <span className="expand-icon">{expanded ? "\u25B2" : "\u25BC"}</span>
      </header>

      {expanded && report.status === "completed" && (
        <div className="kb-report-content">
          {report.report_type === "cluster" && <ClusterContent content={content} />}
          {report.report_type === "association" && <AssociationContent content={content} />}
          {report.report_type === "summary" && <SummaryContent content={content} />}
        </div>
      )}
    </div>
  );
}

function ClusterContent({ content }: { content: Record<string, unknown> }) {
  const clusters = (content.clusters || []) as { theme: string; description: string; trend: string; resource_ids: string[] }[];
  const hotTopics = (content.hot_topics || []) as string[];
  const trends = (content.emerging_trends || []) as string[];

  return (
    <div>
      {clusters.map((c, i) => (
        <div key={i} className="cluster-item">
          <strong>{c.theme}</strong> <span className="trend-badge">{c.trend}</span>
          <p>{c.description}</p>
          <small>{c.resource_ids?.length || 0} articles</small>
        </div>
      ))}
      {hotTopics.length > 0 && (
        <div>
          <h6>Hot Topics</h6>
          <div className="topic-row">{hotTopics.map((t, i) => <span key={i} className="topic-chip">{t}</span>)}</div>
        </div>
      )}
      {trends.length > 0 && (
        <div>
          <h6>Emerging Trends</h6>
          <ul>{trends.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </div>
      )}
    </div>
  );
}

function AssociationContent({ content }: { content: Record<string, unknown> }) {
  const paths = (content.reading_paths || []) as { name: string; description: string; resource_ids: string[] }[];

  return (
    <div>
      {paths.map((p, i) => (
        <div key={i} className="reading-path">
          <strong>{p.name}</strong>
          <p>{p.description}</p>
          <small>{p.resource_ids?.length || 0} articles in path</small>
        </div>
      ))}
    </div>
  );
}

function SummaryContent({ content }: { content: Record<string, unknown> }) {
  const summary = content.executive_summary as string || "";
  const themes = (content.key_themes || []) as { theme: string; summary: string }[];
  const gaps = (content.knowledge_gaps || []) as string[];
  const recs = (content.recommendations || []) as string[];

  return (
    <div>
      <p>{summary}</p>
      {themes.map((t, i) => (
        <div key={i} className="theme-item">
          <strong>{t.theme}</strong>
          <p>{t.summary}</p>
        </div>
      ))}
      {gaps.length > 0 && (
        <div>
          <h6>Knowledge Gaps</h6>
          <ul>{gaps.map((g, i) => <li key={i}>{g}</li>)}</ul>
        </div>
      )}
      {recs.length > 0 && (
        <div>
          <h6>Recommendations</h6>
          <ul>{recs.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
