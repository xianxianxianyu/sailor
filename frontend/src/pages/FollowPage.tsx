import { useEffect, useState } from "react";
import {
  createFollow,
  deleteFollow,
  JobCancelledError,
  JobFailedError,
  JobTimeoutError,
  listBoards,
  listFollows,
  listIssues,
  listResearchPrograms,
  triggerFollowRun,
  updateFollow,
  assertJobSucceeded,
  waitForJob,
} from "../api";
import type { Board, Follow, IssueSnapshot, ResearchProgram } from "../types";
import BoardPage from "./BoardPage";
import ResearchPage from "./ResearchPage";

type FollowContainerTab = "follow" | "boards" | "research";

function FollowTab() {
  const [follows, setFollows] = useState<Follow[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [issues, setIssues] = useState<IssueSnapshot[]>([]);
  const [expandedIssue, setExpandedIssue] = useState("");
  const [boards, setBoards] = useState<Board[]>([]);
  const [programs, setPrograms] = useState<ResearchProgram[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newPolicy, setNewPolicy] = useState("daily");
  const [newBoardIds, setNewBoardIds] = useState<string[]>([]);
  const [newProgramIds, setNewProgramIds] = useState<string[]>([]);
  const [newEnabled, setNewEnabled] = useState(true);
  const [newSchedule, setNewSchedule] = useState("");

  async function loadFollows() {
    setFollows(await listFollows());
  }

  async function loadIssues(id: string) {
    if (!id) { setIssues([]); return; }
    setIssues(await listIssues(id, 5));
  }

  async function loadOptions() {
    const [b, p] = await Promise.all([listBoards(), listResearchPrograms()]);
    setBoards(b);
    setPrograms(p);
  }

  useEffect(() => { loadFollows(); loadOptions(); }, []);
  useEffect(() => { loadIssues(selectedId); }, [selectedId]);

  async function handleCreate() {
    if (!newName.trim()) return;
    setLoading(true);
    setMessage("");
    try {
      const follow = await createFollow({
        name: newName.trim(),
        description: newDesc.trim() || undefined,
        board_ids: newBoardIds,
        research_program_ids: newProgramIds,
        window_policy: newPolicy,
        enabled: newEnabled,
        schedule_minutes: newSchedule ? parseInt(newSchedule) : undefined,
      });
      setNewName(""); setNewDesc(""); setNewBoardIds([]); setNewProgramIds([]); setNewSchedule(""); setShowCreate(false);
      await loadFollows();
      setSelectedId(follow.follow_id);
      setMessage("Follow 创建成功");
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
      await deleteFollow(id);
      if (selectedId === id) { setSelectedId(""); setIssues([]); }
      await loadFollows();
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
      await updateFollow(id, { enabled });
      await loadFollows();
      setMessage(enabled ? "已启用" : "已禁用");
    } catch {
      setMessage("更新失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleRun(id: string) {
    setLoading(true);
    setMessage("");
    try {
      const accepted = await triggerFollowRun(id);
      if (!accepted.job_id) {
        setMessage("运行触发失败：未返回 job_id");
        return;
      }

      setMessage(`后台运行中：status=${accepted.status}，job_id=${accepted.job_id}`);

      const job = await waitForJob(accepted.job_id, 600_000, 1_000);
      assertJobSucceeded(job);

      setMessage(`运行完成（job_id=${accepted.job_id}）`);
      await loadFollows();
      await loadIssues(id);
    } catch (e: unknown) {
      if (e instanceof JobTimeoutError) {
        setMessage(`仍在后台运行（job_id=${e.jobId}，status=${e.lastStatus}）`);
        return;
      }
      if (e instanceof JobCancelledError) {
        setMessage(`运行已取消（job_id=${e.jobId}）`);
        return;
      }
      if (e instanceof JobFailedError) {
        setMessage(`运行失败：${e.errorMessage}（job_id=${e.jobId}）`);
        return;
      }
      const msg = e instanceof Error ? e.message : "触发失败";
      setMessage(msg);
    } finally {
      setLoading(false);
    }
  }

  const selected = follows.find((f) => f.follow_id === selectedId);

  return (
    <div className="page-content">
      <div className="page-header-row">
        <h2>Follow 管理</h2>
        <button className="add-btn" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? "取消" : "+ 新建 Follow"}
        </button>
      </div>

      {message && <p className="message">{message}</p>}

      {showCreate && (
        <div className="create-form">
          <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Follow 名称" />
          <input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="描述（可选）" />
          <select value={newPolicy} onChange={(e) => setNewPolicy(e.target.value)}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
          <label>
            定时运行（分钟）
            <input
              type="number"
              value={newSchedule}
              onChange={(e) => setNewSchedule(e.target.value)}
              placeholder="留空表示不自动运行"
            />
            <small>例如：60 表示每小时运行一次</small>
          </label>
          <div className="checkbox-group">
            <label>Boards:</label>
            {boards.map((b) => (
              <label key={b.board_id}>
                <input
                  type="checkbox"
                  checked={newBoardIds.includes(b.board_id)}
                  onChange={(e) => {
                    if (e.target.checked) setNewBoardIds([...newBoardIds, b.board_id]);
                    else setNewBoardIds(newBoardIds.filter((id) => id !== b.board_id));
                  }}
                />
                {b.name}
              </label>
            ))}
          </div>
          <div className="checkbox-group">
            <label>Research Programs:</label>
            {programs.map((p) => (
              <label key={p.program_id}>
                <input
                  type="checkbox"
                  checked={newProgramIds.includes(p.program_id)}
                  onChange={(e) => {
                    if (e.target.checked) setNewProgramIds([...newProgramIds, p.program_id]);
                    else setNewProgramIds(newProgramIds.filter((id) => id !== p.program_id));
                  }}
                />
                {p.name}
              </label>
            ))}
          </div>
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
          {follows.map((f) => (
            <div
              key={f.follow_id}
              className={`kb-card ${selectedId === f.follow_id ? "kb-card-active" : ""}`}
              onClick={() => setSelectedId(f.follow_id)}
              role="button"
              tabIndex={0}
            >
              <div className="kb-card-info">
                <span className="kb-card-icon">📬</span>
                <div>
                  <div className="kb-card-name">
                    {f.name}
                    {f.enabled ? <span className="enabled-badge">✓</span> : <span className="disabled-badge">✗</span>}
                  </div>
                  {f.last_run_at && <div className="kb-card-desc">上次运行: {new Date(f.last_run_at).toLocaleString()}</div>}
                  {f.error_count > 0 && <div className="error-badge">错误: {f.error_count}</div>}
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
                <button className="enabled-toggle" onClick={() => handleToggleEnabled(selected.follow_id, !selected.enabled)}>
                  {selected.enabled ? "禁用" : "启用"}
                </button>
                <button className="add-btn" onClick={() => handleRun(selected.follow_id)} disabled={loading}>
                  立即运行
                </button>
                <button className="delete-btn" onClick={() => handleDelete(selected.follow_id)} disabled={loading}>
                  删除
                </button>
              </div>
            </div>

            <div className="run-status-row">
              <span className="window-badge">{selected.window_policy}</span>
              {selected.schedule_minutes && <span className="follow-schedule">⏰ 每 {selected.schedule_minutes} 分钟运行一次</span>}
              {selected.last_run_at && <span>上次运行: {new Date(selected.last_run_at).toLocaleString()}</span>}
              {selected.error_count > 0 && <span className="error-text">错误数: {selected.error_count}</span>}
              {selected.last_error && <span className="error-text">最后错误: {selected.last_error}</span>}
            </div>

            <h4>Issue 历史 ({issues.length})</h4>
            {issues.length === 0 ? (
              <p className="empty-hint">暂无 Issue，点击「立即运行」生成</p>
            ) : (
              <div className="issue-list">
                {issues.map((issue) => (
                  <div key={issue.issue_id} className="issue-card">
                    <div
                      className="issue-header"
                      onClick={() => setExpandedIssue(expandedIssue === issue.issue_id ? "" : issue.issue_id)}
                      role="button"
                      tabIndex={0}
                    >
                      <span>{new Date(issue.created_at).toLocaleString()}</span>
                      <span>
                        {issue.window.since && `${issue.window.since} ~ `}
                        {issue.window.until || "now"}
                      </span>
                    </div>
                    {expandedIssue === issue.issue_id && (
                      <div className="issue-sections">
                        {issue.sections.map((sec, idx) => (
                          <div key={idx} className="issue-section">
                            <h5>{sec.source_name || sec.source_id} ({sec.section_type})</h5>
                            {sec.new_items.length > 0 && (
                              <div>
                                <strong>新增 ({sec.new_items.length}):</strong>
                                {sec.new_items.map((item, i) => (
                                  <div key={i} className="issue-item issue-item-new">
                                    {item.url ? <a href={item.url} target="_blank" rel="noreferrer">{item.title || item.item_key}</a> : (item.title || item.item_key)}
                                  </div>
                                ))}
                              </div>
                            )}
                            {sec.removed_items.length > 0 && (
                              <div>
                                <strong>移除 ({sec.removed_items.length}):</strong>
                                {sec.removed_items.map((item, i) => (
                                  <div key={i} className="issue-item issue-item-removed">
                                    {item.url ? <a href={item.url} target="_blank" rel="noreferrer">{item.title || item.item_key}</a> : (item.title || item.item_key)}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function FollowPage() {
  const [activeTab, setActiveTab] = useState<FollowContainerTab>("follow");

  return (
    <div className="page-content">
      <div className="page-tabs">
        <button
          className={`page-tab ${activeTab === "follow" ? "active" : ""}`}
          onClick={() => setActiveTab("follow")}
        >
          📬 关注
        </button>
        <button
          className={`page-tab ${activeTab === "boards" ? "active" : ""}`}
          onClick={() => setActiveTab("boards")}
        >
          📋 看板
        </button>
        <button
          className={`page-tab ${activeTab === "research" ? "active" : ""}`}
          onClick={() => setActiveTab("research")}
        >
          🔬 研究
        </button>
      </div>
      {activeTab === "follow" && <FollowTab />}
      {activeTab === "boards" && <BoardPage />}
      {activeTab === "research" && <ResearchPage />}
    </div>
  );
}
