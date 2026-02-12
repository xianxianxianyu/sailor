import { useState } from "react";
import { addToKnowledgeBase, getKnowledgeBases } from "../api";
import type { KnowledgeBase, TrendingReport } from "../types";

type Props = {
  report: TrendingReport | null;
  loading: boolean;
};

export default function TrendingPage({ report, loading }: Props) {
  const [pickerFor, setPickerFor] = useState<string | null>(null);
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [adding, setAdding] = useState(false);

  async function openPicker(resourceId: string) {
    setPickerFor(resourceId);
    setKbs(await getKnowledgeBases());
  }

  async function handleAdd(kbId: string) {
    if (!pickerFor) return;
    setAdding(true);
    try {
      await addToKnowledgeBase(kbId, pickerFor);
      setPickerFor(null);
    } finally {
      setAdding(false);
    }
  }

  if (loading) {
    return <div className="page-content"><p className="loading-text">正在抓取并分析中，请稍候...</p></div>;
  }

  if (!report || report.groups.length === 0) {
    return (
      <div className="page-content">
        <h2>Trending Report</h2>
        <div className="empty-guide">
          <p>还没有 Trending 数据。点击上方 🚀 一键抓取 开始。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-content">
      <h2>Trending Report</h2>
      <div className="trending-stats">
        共 {report.total_resources} 篇文章，{report.total_tags} 个标签
      </div>

      {report.groups.map((group) => (
        <div key={group.tag_name} className="trending-group">
          <h3 className="trending-tag-header" style={{ borderLeftColor: group.tag_color }}>
            <span className="trending-tag-dot" style={{ backgroundColor: group.tag_color }} />
            {group.tag_name}
            <span className="trending-count">{group.items.length}</span>
          </h3>
          <div className="trending-items">
            {group.items.map((item) => (
              <div key={item.resource_id} className="trending-item">
                <div className="trending-item-main">
                  <a href={item.original_url} target="_blank" rel="noreferrer" className="trending-item-title">
                    {item.title}
                  </a>
                  <p className="trending-item-summary">{item.summary}</p>
                  <div className="trending-item-tags">
                    {item.tags.map((t) => (
                      <span key={t} className="topic-chip">{t}</span>
                    ))}
                  </div>
                </div>
                <button
                  className="trending-add-btn"
                  onClick={() => openPicker(item.resource_id)}
                  title="加入知识库"
                  aria-label={`将 ${item.title} 加入知识库`}
                >+</button>
              </div>
            ))}
          </div>
        </div>
      ))}

      {pickerFor && (
        <div className="modal-backdrop" onClick={() => setPickerFor(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>选择知识库</h3>
            {kbs.length === 0 ? (
              <p className="empty-hint">还没有知识库，请先去 📚 知识库页面创建。</p>
            ) : (
              <div className="kb-picker-list">
                {kbs.map((kb) => (
                  <button
                    key={kb.kb_id}
                    className="kb-picker-item"
                    onClick={() => handleAdd(kb.kb_id)}
                    disabled={adding}
                  >
                    {kb.name}
                    {kb.description && <span className="kb-picker-desc">{kb.description}</span>}
                  </button>
                ))}
              </div>
            )}
            <div className="modal-actions">
              <button onClick={() => setPickerFor(null)}>取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
