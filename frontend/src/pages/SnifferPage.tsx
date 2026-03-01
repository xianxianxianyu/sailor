import { useState } from "react";
import useSnifferWorkspace from "../hooks/useSnifferWorkspace";
import useToast from "../hooks/useToast";
import { createSnifferPack } from "../api";
import SnifferSearchBar from "../components/SnifferSearchBar";
import SnifferResultCard from "../components/SnifferResultCard";
import SnifferInspector from "../components/SnifferInspector";
import SnifferToolsDrawer from "../components/SnifferToolsDrawer";
import ToastContainer from "../components/ToastContainer";
import KBPickerModal from "../components/KBPickerModal";

export default function SnifferPage() {
  const { toasts, toast, dismiss } = useToast();
  const ws = useSnifferWorkspace(toast);
  const [viewMode, setViewMode] = useState<"mixed" | "grouped">("mixed");
  const [toolsOpen, setToolsOpen] = useState(false);

  const channels = ws.response ? [...new Set(ws.response.results.map((r) => r.channel))] : [];

  function onSearch(query: Parameters<typeof ws.handleSearch>[0]) {
    ws.handleSearch(query);
  }

  async function onSavePack(query: {
    keyword: string; channels: string[]; time_range: string;
    sort_by: string; max_results_per_channel: number;
  }) {
    try {
      await createSnifferPack({ name: query.keyword, query });
      toast.success("已保存为嗅探包");
    } catch {
      toast.error("保存嗅探包失败");
    }
  }

  function renderResultList(results: typeof ws.results) {
    return results.map((r) => (
      <SnifferResultCard
        key={r.result_id}
        result={r}
        selected={ws.selectedIds.has(r.result_id)}
        onToggleSelect={ws.toggleSelect}
        onDeepAnalyze={ws.handleDeepAnalyze}
        onSaveToKB={ws.handleSaveToKB}
        onConvertSource={ws.handleConvertSource}
      />
    ));
  }

  return (
    <div className="page-content">
      <div className="sniffer-page-header">
        <h2>资源嗅探</h2>
        <button className="sniffer-action-btn" onClick={() => setToolsOpen(true)}>工具</button>
      </div>
      <SnifferSearchBar onSearch={onSearch} loading={ws.loading} onSavePack={onSavePack} />

      {ws.error && <p className="sniffer-error">{ws.error}</p>}
      {ws.loading && <p className="loading-text">正在跨渠道搜索中...</p>}

      {ws.response && !ws.loading && (
        <div className="sniffer-results-layout">
          <div className="sniffer-results-main">
            <div className="sniffer-view-toggle">
              <button className={`sniffer-tab ${viewMode === "mixed" ? "sniffer-tab-active" : ""}`} onClick={() => setViewMode("mixed")}>
                混排
              </button>
              <button className={`sniffer-tab ${viewMode === "grouped" ? "sniffer-tab-active" : ""}`} onClick={() => setViewMode("grouped")}>
                按来源分组
              </button>
              <span className="sniffer-result-count">共 {ws.response.results.length} 条</span>
            </div>

            {ws.results.length === 0 ? (
              <div className="empty-guide"><p>没有找到相关结果。</p></div>
            ) : viewMode === "mixed" ? (
              <div className="sniffer-result-list">
                {renderResultList(ws.results)}
              </div>
            ) : (
              <div className="sniffer-grouped-results">
                {channels.map((ch) => {
                  const group = ws.results.filter((r) => r.channel === ch);
                  return (
                    <div key={ch} className="sniffer-group">
                      <h3 className="sniffer-group-title">{ch} ({group.length})</h3>
                      <div className="sniffer-result-list">
                        {renderResultList(group)}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {ws.selectedIds.size > 0 && (
              <div className="sniffer-floating-bar">
                <span>已选 {ws.selectedIds.size} 项</span>
                <button onClick={ws.handleCompare} disabled={ws.selectedIds.size < 2}>对比分析</button>
                <button onClick={ws.clearSelection}>取消选择</button>
              </div>
            )}
          </div>

          <aside className="sniffer-sidebar">
            <SnifferInspector
              target={ws.inspectorTarget}
              summary={ws.response.summary}
              results={ws.results}
              analysisResult={ws.analysisResult}
              analysisLoading={ws.analysisLoading}
              analysisTargetId={ws.analysisTargetId}
              onDeepAnalyze={ws.handleDeepAnalyze}
              compareSummary={ws.compareSummary}
              compareLoading={ws.compareLoading}
              onCompare={ws.handleCompare}
              selectedCount={ws.selectedIds.size}
            />
          </aside>
        </div>
      )}

      {!ws.response && !ws.loading && !ws.error && (
        <div className="sniffer-landing">
          <div className="empty-guide">
            <p>输入关键词，跨平台搜索高质量资源。</p>
            <p>支持 Hacker News、GitHub、本地 RSS 订阅源。</p>
          </div>
          <button className="sniffer-action-btn" onClick={() => setToolsOpen(true)}>打开工具面板</button>
        </div>
      )}

      <SnifferToolsDrawer open={toolsOpen} onClose={() => setToolsOpen(false)} onPackRun={ws.handlePackRun} />

      <KBPickerModal
        open={ws.kbPickerOpen}
        resourceTitle={ws.kbPickerResultId}
        knownKbIds={[]}
        knowledgeBases={ws.kbs}
        submitting={ws.kbSubmitting}
        onCancel={() => ws.setKbPickerOpen(false)}
        onConfirm={ws.handleKBConfirm}
      />

      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </div>
  );
}
