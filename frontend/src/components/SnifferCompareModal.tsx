import type { CompareSummary } from "../types";

type Props = {
  open: boolean;
  loading: boolean;
  summary: CompareSummary | null;
  onClose: () => void;
};

export default function SnifferCompareModal({ open, loading, summary, onClose }: Props) {
  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal sniffer-compare-modal" onClick={(e) => e.stopPropagation()}>
        <h3>对比分析</h3>

        {loading && <p className="loading-text">正在对比分析中...</p>}

        {summary && !loading && (
          <>
            <div className="sniffer-compare-dims">
              {summary.dimensions.map((dim, i) => (
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
              <p>{summary.verdict}</p>
              <small>模型: {summary.model}</small>
            </div>
          </>
        )}

        <div className="modal-actions">
          <button onClick={onClose}>关闭</button>
        </div>
      </div>
    </div>
  );
}
