import { useEffect, useState } from "react";
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  getKBItems,
  getKnowledgeBases,
  removeKBItem,
} from "../api";
import type { KBItemResource, KnowledgeBase } from "../types";
import KBGraphView from "../components/KBGraphView";
import KBReportPanel from "../components/KBReportPanel";
import TagPage from "./TagPage";

type KBTab = "articles" | "graph" | "tags" | "reports";

export default function KBPage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [selectedKb, setSelectedKb] = useState<string>("");
  const [items, setItems] = useState<KBItemResource[]>([]);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [activeTab, setActiveTab] = useState<KBTab>("articles");

  async function loadKbs() {
    const list = await getKnowledgeBases();
    setKbs(list);
  }

  async function loadItems(kbId: string) {
    if (!kbId) { setItems([]); return; }
    setItems(await getKBItems(kbId));
  }

  useEffect(() => { loadKbs(); }, []);
  useEffect(() => { loadItems(selectedKb); }, [selectedKb]);
  useEffect(() => { setActiveTab("articles"); }, [selectedKb]);

  async function handleCreate() {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const kb = await createKnowledgeBase(newName.trim(), newDesc.trim() || undefined);
      setNewName(""); setNewDesc(""); setShowCreate(false);
      await loadKbs();
      setSelectedKb(kb.kb_id);
    } finally {
      setCreating(false);
    }
  }

  async function handleDeleteKb(kbId: string) {
    await deleteKnowledgeBase(kbId);
    if (selectedKb === kbId) { setSelectedKb(""); setItems([]); }
    await loadKbs();
  }

  async function handleRemoveItem(resourceId: string) {
    await removeKBItem(selectedKb, resourceId);
    await loadItems(selectedKb);
  }

  const selectedKbObj = kbs.find((kb) => kb.kb_id === selectedKb);

  return (
    <div className="page-content">
      <div className="page-header-row">
        <h2>知识库管理</h2>
        <button className="add-btn" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? "取消" : "+ 创建知识库"}
        </button>
      </div>

      {showCreate && (
        <div className="create-form">
          <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="知识库名称" />
          <input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="描述（可选）" />
          <button onClick={handleCreate} disabled={creating} className="add-btn">
            {creating ? "创建中..." : "创建"}
          </button>
        </div>
      )}

      {kbs.length === 0 && !showCreate ? (
        <div className="empty-guide">
          <p>还没有知识库。创建一个来收藏你感兴趣的文章吧。</p>
        </div>
      ) : (
        <div className="kb-page-layout">
          <div className="kb-card-list">
            {kbs.map((kb) => (
              <div
                key={kb.kb_id}
                className={`kb-card ${selectedKb === kb.kb_id ? "kb-card-active" : ""}`}
                onClick={() => setSelectedKb(kb.kb_id)}
                role="button"
                tabIndex={0}
              >
                <div className="kb-card-info">
                  <span className="kb-card-icon">📚</span>
                  <div>
                    <div className="kb-card-name">{kb.name}</div>
                    {kb.description && <div className="kb-card-desc">{kb.description}</div>}
                  </div>
                </div>
                <button
                  className="delete-btn-sm"
                  onClick={(e) => { e.stopPropagation(); handleDeleteKb(kb.kb_id); }}
                  aria-label={`删除 ${kb.name}`}
                >×</button>
              </div>
            ))}
          </div>

          {selectedKb && (
            <div className="kb-detail">
              <div className="kb-tab-bar">
                <button
                  className={`kb-tab ${activeTab === "articles" ? "kb-tab-active" : ""}`}
                  onClick={() => setActiveTab("articles")}
                >
                  收藏文章 ({items.length})
                </button>
                <button
                  className={`kb-tab ${activeTab === "graph" ? "kb-tab-active" : ""}`}
                  onClick={() => setActiveTab("graph")}
                >
                  Graph
                </button>
                <button
                  className={`kb-tab ${activeTab === "tags" ? "kb-tab-active" : ""}`}
                  onClick={() => setActiveTab("tags")}
                >
                  🏷️ 标签
                </button>
                <button
                  className={`kb-tab ${activeTab === "reports" ? "kb-tab-active" : ""}`}
                  onClick={() => setActiveTab("reports")}
                >
                  📊 报告
                </button>
              </div>

              {activeTab === "articles" && (
                <>
                  {items.length === 0 ? (
                    <p className="empty-hint">这个知识库还没有文章。去 📊 趋势页面收藏吧。</p>
                  ) : (
                    <div className="kb-items-grid">
                      {items.map((item) => (
                        <div key={item.resource_id} className="kb-item-card">
                          <a href={item.original_url} target="_blank" rel="noreferrer" className="kb-item-title">
                            {item.title}
                          </a>
                          <p className="kb-item-summary">{item.summary}</p>
                          <div className="kb-item-footer">
                            <div className="kb-item-tags">
                              {item.topics.map((t) => <span key={t} className="topic-chip">{t}</span>)}
                            </div>
                            <button
                              className="delete-btn"
                              onClick={() => handleRemoveItem(item.resource_id)}
                              aria-label={`移除 ${item.title}`}
                            >移除</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}

              {activeTab === "graph" && <KBGraphView kbId={selectedKb} />}
              {activeTab === "tags" && <TagPage />}
              {activeTab === "reports" && <KBReportPanel kbId={selectedKb} />}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
