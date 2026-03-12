import { useState } from "react";
import type { SniffResult } from "../types";

const CHANNEL_ICONS: Record<string, string> = {
  hackernews: "🟠",
  github: "🐙",
  rss: "📡",
};

type Props = {
  result: SniffResult;
  selected?: boolean;
  onToggleSelect?: (id: string) => void;
  onDeepAnalyze?: (id: string) => void | Promise<void>;
  onSaveToKB?: (id: string) => void;
  onConvertSource?: (id: string) => void;
};

export default function SnifferResultCard({
  result,
  selected,
  onToggleSelect,
  onDeepAnalyze,
  onSaveToKB,
  onConvertSource,
}: Props) {
  const icon = CHANNEL_ICONS[result.channel] || "🔗";
  const metrics = result.metrics;
  const [busy, setBusy] = useState("");

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "";
    try {
      return new Date(dateStr).toLocaleDateString("zh-CN", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return "";
    }
  }

  return (
    <div className={`sniffer-result-card ${selected ? "sniffer-result-selected" : ""}`}>
      <div className="sniffer-result-header">
        {onToggleSelect && (
          <input
            type="checkbox"
            className="sniffer-result-checkbox"
            checked={selected || false}
            onChange={() => onToggleSelect(result.result_id)}
          />
        )}
        <span className="sniffer-result-channel" title={result.channel}>{icon}</span>
        <a href={result.url} target="_blank" rel="noreferrer" className="sniffer-result-title">
          {result.title}
        </a>
      </div>

      {result.snippet && <p className="sniffer-result-snippet">{result.snippet}</p>}

      <div className="sniffer-result-meta">
        {result.author && <span className="sniffer-result-author">{result.author}</span>}
        {result.published_at && <span className="sniffer-result-date">{formatDate(result.published_at)}</span>}
        <span className="sniffer-result-type">{result.media_type}</span>
        {metrics.likes != null && metrics.likes > 0 && <span className="sniffer-metric">👍 {metrics.likes}</span>}
        {metrics.comments != null && metrics.comments > 0 && <span className="sniffer-metric">💬 {metrics.comments}</span>}
        {metrics.stars != null && metrics.stars > 0 && <span className="sniffer-metric">⭐ {metrics.stars}</span>}
        {metrics.forks != null && metrics.forks > 0 && <span className="sniffer-metric">🔀 {metrics.forks}</span>}
      </div>

      <div className="sniffer-result-actions">
        {onDeepAnalyze && (
          <button
            className="sniffer-action-btn"
            disabled={busy === "analyze"}
            onClick={async () => {
              setBusy("analyze");
              try {
                await onDeepAnalyze(result.result_id);
              } finally {
                setBusy("");
              }
            }}
          >
            {busy === "analyze" ? "分析中..." : "深度分析"}
          </button>
        )}
        {onSaveToKB && (
          <button className="sniffer-action-btn" onClick={() => onSaveToKB(result.result_id)}>
            收藏
          </button>
        )}
        {onConvertSource && (
          <button className="sniffer-action-btn" onClick={() => onConvertSource(result.result_id)}>
            转订阅
          </button>
        )}
      </div>
    </div>
  );
}
