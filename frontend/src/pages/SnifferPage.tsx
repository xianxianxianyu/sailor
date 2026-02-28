import { useState } from "react";
import {
  snifferSearch,
  deepAnalyze,
  compareResults,
  saveToKB,
  convertToSource,
  getKnowledgeBases,
} from "../api";
import SnifferSearchBar from "../components/SnifferSearchBar";
import SnifferResultCard from "../components/SnifferResultCard";
import SnifferSummaryPanel from "../components/SnifferSummaryPanel";
import SnifferCompareModal from "../components/SnifferCompareModal";
import SnifferPackPanel from "../components/SnifferPackPanel";
import SnifferHealthPanel from "../components/SnifferHealthPanel";
import KBPickerModal from "../components/KBPickerModal";
import type {
  CompareSummary,
  KnowledgeBase,
  ResourceAnalysis,
  SearchResponse,
  SniffResult,
} from "../types";

export default function SnifferPage() {
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<string>("all");

  // Multi-select
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Compare modal
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareSummary, setCompareSummary] = useState<CompareSummary | null>(null);

  // Deep analyze
  const [analysisResult, setAnalysisResult] = useState<ResourceAnalysis | null>(null);
  const [analysisOpen, setAnalysisOpen] = useState(false);

  // KB picker
  const [kbPickerOpen, setKbPickerOpen] = useState(false);
  const [kbPickerResultId, setKbPickerResultId] = useState("");
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [kbSubmitting, setKbSubmitting] = useState(false);

  // Side panel tab
  const [sideTab, setSideTab] = useState<"summary" | "packs" | "health">("summary");

  async function handleSearch(query: {
    keyword: string; channels: string[]; time_range: string;
    sort_by: string; max_results_per_channel: number;
  }) {
    setLoading(true); setError(""); setActiveTab("all"); setSelectedIds(new Set());
    try { setResponse(await snifferSearch(query)); }
    catch { setError("搜索失败，请检查网络或稍后重试。"); }
    finally { setLoading(false); }
  }

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function handleCompare() {
    if (selectedIds.size < 2) return;
    setCompareOpen(true); setCompareLoading(true); setCompareSummary(null);
    try { setCompareSummary(await compareResults([...selectedIds])); }
    catch { /* ignore */ }
    setCompareLoading(false);
  }

  async function handleDeepAnalyze(resultId: string) {
    try {
      const a = await deepAnalyze(resultId);
      setAnalysisResult(a); setAnalysisOpen(true);
    } catch { /* ignore */ }
  }

  async function handleSaveToKB(resultId: string) {
    setKbPickerResultId(resultId);
    try { setKbs(await getKnowledgeBases()); } catch { /* ignore */ }
    setKbPickerOpen(true);
  }

  async function handleKBConfirm(kbId: string) {
    setKbSubmitting(true);
    try { await saveToKB(kbPickerResultId, kbId); } catch { /* ignore */ }
    setKbSubmitting(false); setKbPickerOpen(false);
  }

  async function handleConvertSource(resultId: string) {
    try { await convertToSource(resultId); } catch { /* ignore */ }
  }

  function handlePackRun(res: unknown) {
    setResponse(res as SearchResponse);
    setActiveTab("all"); setSelectedIds(new Set());
  }

  const channels = response ? [...new Set(response.results.map((r) => r.channel))] : [];
  const filteredResults: SniffResult[] = response
    ? activeTab === "all" ? response.results : response.results.filter((r) => r.channel === activeTab)
    : [];

  return (
    <div className="page-content">
      <h2>资源嗅探</h2>
      <SnifferSearchBar onSearch={handleSearch} loading={loading} />

      {error && <p className="sniffer-error">{error}</p>}
      {loading && <p className="loading-text">正在跨渠道搜索中...</p>}

      {response && !loading && (
        <div className="sniffer-results-layout">
          <div className="sniffer-results-main">
            <div className="sniffer-tabs">
              <button className={`sniffer-tab ${activeTab === "all" ? "sniffer-tab-active" : ""}`} onClick={() => setActiveTab("all")}>
                全部 ({response.results.length})
              </button>
              {channels.map((ch) => (
                <button key={ch} className={`sniffer-tab ${activeTab === ch ? "sniffer-tab-active" : ""}`} onClick={() => setActiveTab(ch)}>
                  {ch} ({response.results.filter((r) => r.channel === ch).length})
                </button>
              ))}
            </div>

            {filteredResults.length === 0 ? (
              <div className="empty-guide"><p>没有找到相关结果。</p></div>
            ) : (
              <div className="sniffer-result-list">
                {filteredResults.map((r) => (
                  <SnifferResultCard
                    key={r.result_id}
                    result={r}
                    selected={selectedIds.has(r.result_id)}
                    onToggleSelect={toggleSelect}
                    onDeepAnalyze={handleDeepAnalyze}
                    onSaveToKB={handleSaveToKB}
                    onConvertSource={handleConvertSource}
                  />
                ))}
              </div>
            )}

            {selectedIds.size > 0 && (
              <div className="sniffer-floating-bar">
                <span>已选 {selectedIds.size} 项</span>
                <button onClick={handleCompare} disabled={selectedIds.size < 2}>对比分析</button>
                <button onClick={() => setSelectedIds(new Set())}>取消选择</button>
              </div>
            )}
          </div>

          <aside className="sniffer-sidebar">
            <div className="sniffer-side-tabs">
              <button className={sideTab === "summary" ? "active" : ""} onClick={() => setSideTab("summary")}>摘要</button>
              <button className={sideTab === "packs" ? "active" : ""} onClick={() => setSideTab("packs")}>嗅探包</button>
              <button className={sideTab === "health" ? "active" : ""} onClick={() => setSideTab("health")}>状态</button>
            </div>
            {sideTab === "summary" && <SnifferSummaryPanel summary={response.summary} />}
            {sideTab === "packs" && <SnifferPackPanel onPackRun={handlePackRun} />}
            {sideTab === "health" && <SnifferHealthPanel />}
          </aside>
        </div>
      )}

      {!response && !loading && !error && (
        <div className="sniffer-landing">
          <div className="empty-guide">
            <p>输入关键词，跨平台搜索高质量资源。</p>
            <p>支持 Hacker News、GitHub、本地 RSS 订阅源。</p>
          </div>
          <div className="sniffer-landing-panels">
            <SnifferPackPanel onPackRun={handlePackRun} />
            <SnifferHealthPanel />
          </div>
        </div>
      )}

      {/* Modals */}
      <SnifferCompareModal
        open={compareOpen}
        loading={compareLoading}
        summary={compareSummary}
        onClose={() => setCompareOpen(false)}
      />

      <KBPickerModal
        open={kbPickerOpen}
        resourceTitle={kbPickerResultId}
        knownKbIds={[]}
        knowledgeBases={kbs}
        submitting={kbSubmitting}
        onCancel={() => setKbPickerOpen(false)}
        onConfirm={handleKBConfirm}
      />

      {analysisOpen && analysisResult && (
        <div className="modal-backdrop" onClick={() => setAnalysisOpen(false)}>
          <div className="modal sniffer-analysis-modal" onClick={(e) => e.stopPropagation()}>
            <h3>深度分析结果</h3>
            {analysisResult.status === "completed" ? (
              <>
                <p><strong>摘要:</strong> {analysisResult.summary}</p>
                <p><strong>主题:</strong> {analysisResult.topics.join(", ")}</p>
                <p><strong>评分:</strong> 深度 {analysisResult.scores.depth} / 实用 {analysisResult.scores.utility} / 新颖 {analysisResult.scores.novelty}</p>
                <small>模型: {analysisResult.model}</small>
              </>
            ) : (
              <p>分析失败: {analysisResult.error_message}</p>
            )}
            <div className="modal-actions">
              <button onClick={() => setAnalysisOpen(false)}>关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
