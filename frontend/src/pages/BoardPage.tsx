import { useEffect, useState } from "react";
import {
  createBoard,
  deleteBoard,
  getLatestSnapshot,
  JobCancelledError,
  JobFailedError,
  JobTimeoutError,
  listBoards,
  listSnapshotItems,
  triggerBoardSnapshot,
  updateBoard,
  assertJobSucceeded,
  waitForJob,
} from "../api";
import type { Board, BoardSnapshot, BoardSnapshotItem } from "../types";

export default function BoardPage() {
  const [boards, setBoards] = useState<Board[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [snapshot, setSnapshot] = useState<BoardSnapshot | null>(null);
  const [items, setItems] = useState<BoardSnapshotItem[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const [newProvider, setNewProvider] = useState("github");
  const [newKind, setNewKind] = useState("trending");
  const [newName, setNewName] = useState("");
  const [newEnabled, setNewEnabled] = useState(true);

  async function loadBoards() {
    setBoards(await listBoards());
  }

  async function loadSnapshot(id: string) {
    if (!id) { setSnapshot(null); setItems([]); return; }
    const snap = await getLatestSnapshot(id);
    setSnapshot(snap);
    if (snap) {
      setItems(await listSnapshotItems(snap.snapshot_id));
    } else {
      setItems([]);
    }
  }

  useEffect(() => { loadBoards(); }, []);
  useEffect(() => { loadSnapshot(selectedId); }, [selectedId]);

  async function handleCreate() {
    if (!newName.trim()) return;
    setLoading(true);
    setMessage("");
    try {
      const board = await createBoard({ provider: newProvider, kind: newKind, name: newName.trim(), enabled: newEnabled });
      setNewName(""); setShowCreate(false);
      await loadBoards();
      setSelectedId(board.board_id);
      setMessage("Board 创建成功");
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
      await deleteBoard(id);
      if (selectedId === id) { setSelectedId(""); setSnapshot(null); setItems([]); }
      await loadBoards();
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
      await updateBoard(id, { enabled });
      await loadBoards();
      setMessage(enabled ? "已启用" : "已禁用");
    } catch {
      setMessage("更新失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleSnapshot(id: string) {
    setLoading(true);
    setMessage("");
    try {
      const accepted = await triggerBoardSnapshot(id);
      if (!accepted.job_id) {
        setMessage("快照采集触发失败：未返回 job_id");
        return;
      }

      setMessage(`快照采集已入队：status=${accepted.status}，job_id=${accepted.job_id}`);

      const job = await waitForJob(accepted.job_id, 600_000, 1_000);
      assertJobSucceeded(job);

      setMessage(`快照采集完成（job_id=${accepted.job_id}）`);
      await loadBoards();
      await loadSnapshot(id);
    } catch (e: unknown) {
      if (e instanceof JobTimeoutError) {
        setMessage(`仍在后台运行（job_id=${e.jobId}，status=${e.lastStatus}）`);
        return;
      }
      if (e instanceof JobCancelledError) {
        setMessage(`快照采集已取消（job_id=${e.jobId}）`);
        return;
      }
      if (e instanceof JobFailedError) {
        setMessage(`快照采集失败：${e.errorMessage}（job_id=${e.jobId}）`);
        return;
      }
      const msg = e instanceof Error ? e.message : "触发失败";
      setMessage(msg);
    } finally {
      setLoading(false);
    }
  }

  const selected = boards.find((b) => b.board_id === selectedId);

  return (
    <div className="page-content">
      <div className="page-header-row">
        <h2>Boards 管理</h2>
        <button className="add-btn" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? "取消" : "+ 新建 Board"}
        </button>
      </div>

      {message && <p className="message">{message}</p>}

      {showCreate && (
        <div className="create-form">
          <select value={newProvider} onChange={(e) => setNewProvider(e.target.value)}>
            <option value="github">GitHub</option>
            <option value="huggingface">HuggingFace</option>
          </select>
          <input value={newKind} onChange={(e) => setNewKind(e.target.value)} placeholder="Kind (默认 trending)" />
          <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Board 名称" />
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
          {boards.map((b) => (
            <div
              key={b.board_id}
              className={`kb-card ${selectedId === b.board_id ? "kb-card-active" : ""}`}
              onClick={() => setSelectedId(b.board_id)}
              role="button"
              tabIndex={0}
            >
              <div className="kb-card-info">
                <span className="kb-card-icon">📋</span>
                <div>
                  <div className="kb-card-name">
                    {b.name}
                    <span className={`provider-badge provider-${b.provider}`}>{b.provider}</span>
                    {b.enabled ? <span className="enabled-badge">✓</span> : <span className="disabled-badge">✗</span>}
                  </div>
                  {b.last_run_at && <div className="kb-card-desc">上次采集: {new Date(b.last_run_at).toLocaleString()}</div>}
                </div>
              </div>
            </div>
          ))}
        </div>

        {selected && (
          <div className="kb-detail">
            <div className="detail-header">
              <h3>{selected.name}</h3>
              <div className="detail-actions">
                <button className="enabled-toggle" onClick={() => handleToggleEnabled(selected.board_id, !selected.enabled)}>
                  {selected.enabled ? "禁用" : "启用"}
                </button>
                <button className="add-btn" onClick={() => handleSnapshot(selected.board_id)} disabled={loading}>
                  采集快照
                </button>
                <button className="delete-btn" onClick={() => handleDelete(selected.board_id)} disabled={loading}>
                  删除
                </button>
              </div>
            </div>

            <div className="run-status-row">
              <span className={`provider-badge provider-${selected.provider}`}>{selected.provider}</span>
              <span className="window-badge">{selected.kind}</span>
              {selected.last_run_at && <span>上次采集: {new Date(selected.last_run_at).toLocaleString()}</span>}
            </div>

            {snapshot ? (
              <div>
                <div className="snapshot-meta">
                  快照时间: {new Date(snapshot.captured_at).toLocaleString()} · {items.length} 条
                </div>
                <div className="snapshot-list">
                  {items.map((item) => (
                    <div key={item.item_key} className="snapshot-item">
                      <span className="snapshot-rank">#{item.source_order}</span>
                      {item.url ? (
                        <a href={item.url} target="_blank" rel="noreferrer">{item.title || item.item_key}</a>
                      ) : (
                        <span>{item.title || item.item_key}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="empty-hint">尚无快照，点击「采集快照」开始</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
