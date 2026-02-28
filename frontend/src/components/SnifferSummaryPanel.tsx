import type { SearchSummary } from "../types";

type Props = {
  summary: SearchSummary;
};

export default function SnifferSummaryPanel({ summary }: Props) {
  if (summary.total === 0) return null;

  return (
    <div className="sniffer-summary-panel">
      <h3 className="sniffer-summary-title">搜索摘要</h3>

      <div className="sniffer-summary-stat">
        共找到 <strong>{summary.total}</strong> 条结果
      </div>

      <div className="sniffer-summary-section">
        <h4>渠道分布</h4>
        <div className="sniffer-channel-bars">
          {Object.entries(summary.channel_distribution).map(([ch, count]) => (
            <div key={ch} className="sniffer-bar-row">
              <span className="sniffer-bar-label">{ch}</span>
              <div className="sniffer-bar-track">
                <div
                  className="sniffer-bar-fill"
                  style={{ width: `${Math.min((count / summary.total) * 100, 100)}%` }}
                />
              </div>
              <span className="sniffer-bar-count">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {summary.keyword_clusters.length > 0 && (
        <div className="sniffer-summary-section">
          <h4>关键词聚类</h4>
          <div className="sniffer-keyword-chips">
            {summary.keyword_clusters.map((kw) => (
              <span key={kw.word} className="sniffer-keyword-chip">
                {kw.word} <small>({kw.count})</small>
              </span>
            ))}
          </div>
        </div>
      )}

      {summary.top_by_engagement.length > 0 && (
        <div className="sniffer-summary-section">
          <h4>热门内容</h4>
          <ol className="sniffer-top-list">
            {summary.top_by_engagement.map((item) => (
              <li key={item.result_id}>
                {item.title} <small>({item.channel}, {item.engagement})</small>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
