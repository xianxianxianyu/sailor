import { useEffect, useState } from "react";
import {
  createResearchProgram,
  deleteResearchProgram,
  getResearchProgram,
  getSources,
  listResearchPrograms,
  updateResearchProgram,
} from "../api";
import type { ResearchProgram, SourceRecord } from "../types";

export default function ResearchPage() {
  const [programs, setPrograms] = useState<ResearchProgram[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [selectedProgram, setSelectedProgram] = useState<ResearchProgram | null>(null);
  const [allSources, setAllSources] = useState<SourceRecord[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newEnabled, setNewEnabled] = useState(true);

  const [editedSourceIds, setEditedSourceIds] = useState<string[]>([]);
  const [editedFilters, setEditedFilters] = useState("");

  async function loadPrograms() {
    setPrograms(await listResearchPrograms());
  }

  async function loadSources() {
    setAllSources(await getSources());
  }

  async function loadProgramDetail(id: string) {
    if (!id) {
      setSelectedProgram(null);
      return;
    }
    try {
      const program = await getResearchProgram(id);
      setSelectedProgram(program);
      setEditedSourceIds(program.source_ids || []);
      setEditedFilters(JSON.stringify(program.filters || {}, null, 2));
    } catch {
      setMessage("加载详情失败");
    }
  }

  useEffect(() => {
    loadPrograms();
    loadSources();
  }, []);

  useEffect(() => {
    loadProgramDetail(selectedId);
  }, [selectedId]);

  async function handleCreate() {
    if (!newName.trim()) return;
    setLoading(true);
    setMessage("");
    try {
      const program = await createResearchProgram({
        name: newName.trim(),
        description: newDesc.trim() || undefined,
        enabled: newEnabled,
      });
      setNewName("");
      setNewDesc("");
      setShowCreate(false);
      await loadPrograms();
      setSelectedId(program.program_id);
      setMessage("Research Program 创建成功");
    } catch {
      setMessage("创建失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id: string) {
    setLoading(true);
    setMessage("");
    try {
      await deleteResearchProgram(id);
      if (selectedId === id) {
        setSelectedId("");
        setSelectedProgram(null);
      }
      await loadPrograms();
      setMessage("已删除");
    } catch {
      setMessage("删除失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleToggleEnabled(id: string, enabled: boolean) {
    setLoading(true);
    setMessage("");
    try {
      await updateResearchProgram(id, { enabled });
      await loadPrograms();
      await loadProgramDetail(id);
      setMessage(enabled ? "已启用" : "已禁用");
    } catch {
      setMessage("更新失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (!selectedProgram) return;
    setLoading(true);
    setMessage("");
    try {
      let parsedFilters: Record<string, unknown> | undefined;
      try {
        parsedFilters = editedFilters.trim() ? JSON.parse(editedFilters) : undefined;
      } catch {
        setMessage("Filters JSON 格式错误");
        setLoading(false);
        return;
      }

      await updateResearchProgram(selectedProgram.program_id, {
        source_ids: editedSourceIds,
        filters: parsedFilters,
      });
      await loadPrograms();
      await loadProgramDetail(selectedProgram.program_id);
      setMessage("保存成功");
    } catch {
      setMessage("保存失败");
    } finally {
      setLoading(false);
    }
  }

  function handleSourceToggle(sourceId: string, checked: boolean) {
    if (checked) {
      setEditedSourceIds([...editedSourceIds, sourceId]);
    } else {
      setEditedSourceIds(editedSourceIds.filter((id) => id !== sourceId));
    }
  }

  return (
    <div className="page-content">
      <div className="page-header-row">
        <h2>Research Programs</h2>
        <button className="add-btn" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? "取消" : "+ 新建 Program"}
        </button>
      </div>

      {message && <p className="message">{message}</p>}

      {showCreate && (
        <div className="create-form">
          <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Program 名称" />
          <input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="描述（可选）" />
          <label>
            <input type="checkbox" checked={newEnabled} onChange={(e) => setNewEnabled(e.target.checked)} />
            启用
          </label>
          <button onClick={handleCreate} disabled={loading} className="add-btn">
            {loading ? "创建中..." : "创建"}
          </button>
        </div>
      )}

      <div className="kb-page-layout">
        <div className="kb-card-list">
          {programs.map((p) => (
            <div
              key={p.program_id}
              className={`kb-card ${selectedId === p.program_id ? "kb-card-active" : ""}`}
              onClick={() => setSelectedId(p.program_id)}
              role="button"
              tabIndex={0}
            >
              <div className="kb-card-info">
                <span className="kb-card-icon">🔬</span>
                <div>
                  <div className="kb-card-name">
                    {p.name}
                    {p.enabled ? <span className="enabled-badge">✓</span> : <span className="disabled-badge">✗</span>}
                  </div>
                  <div className="kb-card-desc">
                    {p.source_ids.length} 个来源
                    {p.last_run_at && ` · ${new Date(p.last_run_at).toLocaleString()}`}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {selectedProgram && (
          <div className="kb-detail">
            <div className="detail-header">
              <h3>{selectedProgram.name}</h3>
              <div className="detail-actions">
                <button className="enabled-toggle" onClick={() => handleToggleEnabled(selectedProgram.program_id, !selectedProgram.enabled)}>
                  {selectedProgram.enabled ? "禁用" : "启用"}
                </button>
                <button className="add-btn" onClick={handleSave} disabled={loading}>
                  保存配置
                </button>
                <button className="delete-btn" onClick={() => handleDelete(selectedProgram.program_id)} disabled={loading}>
                  删除
                </button>
              </div>
            </div>

            {selectedProgram.description && (
              <div className="research-description">{selectedProgram.description}</div>
            )}

            <div className="research-detail">
              <div className="research-sources">
                <h4>关联订阅源</h4>
                {allSources.length === 0 ? (
                  <p className="empty-hint">暂无可用订阅源</p>
                ) : (
                  <div className="checkbox-group">
                    {allSources.map((source) => (
                      <label key={source.source_id}>
                        <input
                          type="checkbox"
                          checked={editedSourceIds.includes(source.source_id)}
                          onChange={(e) => handleSourceToggle(source.source_id, e.target.checked)}
                        />
                        {source.name} <span className="source-type-badge">({source.source_type})</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>

              <div className="research-filters">
                <h4>过滤条件（JSON）</h4>
                <textarea
                  value={editedFilters}
                  onChange={(e) => setEditedFilters(e.target.value)}
                  rows={8}
                  placeholder='{"topic": "AI", "min_score": 0.7}'
                />
                <small>配置过滤规则，留空表示不过滤</small>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
