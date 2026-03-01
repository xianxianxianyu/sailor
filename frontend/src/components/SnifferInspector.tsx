import type { InspectorTarget } from "../hooks/useSnifferWorkspace";
import type { CompareSummary, ResourceAnalysis, SearchSummary, SniffResult } from "../types";
import SnifferSummaryPanel from "./SnifferSummaryPanel";

type Props = {
  target: InspectorTarget | null;
  summary: SearchSummary | null;
  results: SniffResult[];
  // detail
  analysisResult: ResourceAnalysis | null;
  analysisLoading: boolean;
  analysisTargetId: string | null;
  onDeepAnalyze: (id: string) => void;
  // compare
  compareSummary: CompareSummary | null;
  compareLoading: boolean;
  onCompare: () => void;
  selectedCount: number;
};

export default function SnifferInspector({
  target,
  summary,
  results,
  analysisResult,
  analysisLoading,
  analysisTargetId,
  onDeepAnalyze,
  compareSummary,
  compareLoading,
  onCompare,
  selectedCount,
}: Props) {
  if (!target) {
    return (
      <div className="sniffer-inspector sniffer-inspector-empty">
        <p>搜索后在此查看摘要与分析结果</p>
      </div>
    );
  }

  if (target.kind === "summary") {
    return (
      <div className="sniffer-inspector">
        {summary && <SnifferSummaryPanel summary={summary} />}
      </div>
    );
  }

  if (target.kind === "detail") {
    const item = results.find((r) => r.result_id === target.resultId);
    return (
      <div className="sniffer-inspector">
        <h3 className="sniffer-inspector-title">资源详情</h3>
        {item ? (
          <div className="sniffer-inspector-detail">
            <a href={item.url} target="_blank" rel="noreferrer" className="sniffer-inspector-link">{item.title}</a>
            {item.snippet && <p className="sniffer-inspector-snippet">{item.snippet}</p>}
            <div className="sniffer-inspector-meta">
              {item.author && <span>作者: {item.author}</span>}
              <span>渠道: {item.channel}</span>
              <span>类型: {item.media_type}</span>
            </div>
          </div>
        ) : (
          <p>未找到该资源</p>
        )}

        <div className="sniffer-inspector-section">
          <h4>深度分析</h4>
          {analysisLoading && analysisTargetId === target.resultId && (
            <p className="loading-text">正在分析中...</p>
          )}
          {analysisResult && analysisTargetId === target.resultId ? (
            analysisResult.status === "completed" ? (
              <div className="sniffer-inspector-analysis">
                <p><strong>摘要:</strong> {analysisResult.summary}</p>
                <p><strong>主题:</strong> {analysisResult.topics.join(", ")}</p>
                <p><strong>评分:</strong> 深度 {analysisResult.scores.depth} / 实用 {analysisResult.scores.utility} / 新颖 {analysisResult.scores.novelty}</p>
                <small>模型: {analysisResult.model}</small>
              </div>
            ) : (
              <p className="sniffer-error">分析失败: {analysisResult.error_message}</p>
            )
          ) : !analysisLoading ? (
            <button className="sniffer-action-btn" onClick={() => onDeepAnalyze(target.resultId)}>
              开始深度分析
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  // target.kind === "compare"
  return (
    <div className="sniffer-inspector">
      <h3 className="sniffer-inspector-title">对比分析 ({selectedCount} 项)</h3>

      {compareLoading && <p className="loading-text">正在对比分析中...</p>}

      {!compareSummary && !compareLoading && (
        <button className="sniffer-action-btn" onClick={onCompare} disabled={selectedCount < 2}>
          开始对比分析
        </button>
      )}

      {compareSummary && !compareLoading && (
        <div className="sniffer-inspector-compare">
          <div className="sniffer-compare-dims">
            {compareSummary.dimensions.map((dim, i) => (
              <div key={i} className="sniffer-compare-dim">
                <h4>{dim.name}</h4>
                <table className="sniffer-compare-table">
                  <thead>
                    <tr><th>资源</th><th>评分</th><th>评价</th></tr>
                  </thead>
                  <tbody>
                    {dim.items.map((item, j) => (
                      <tr key={j}>
                        <td>{item.title}</td>
                        <td><span className="sniffer-score">{item.score}/10</span></td>
                        <td>{item.comment}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
          <div className="sniffer-compare-verdict">
            <h4>综合结论</h4>
            <p>{compareSummary.verdict}</p>
            <small>模型: {compareSummary.model}</small>
          </div>
        </div>
      )}
    </div>
  );
}