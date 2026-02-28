import { useState } from "react";

import { getTrending, runFullPipeline } from "./api";
import NavBar from "./components/NavBar";
import LogPanel from "./components/LogPanel";
import LLMSettingsModal from "./components/LLMSettingsModal";
import type { ViewId } from "./components/NavBar";
import FeedPage from "./pages/FeedPage";
import KBPage from "./pages/KBPage";
import SnifferPage from "./pages/SnifferPage";
import TagPage from "./pages/TagPage";
import TrendingPage from "./pages/TrendingPage";
import type { TrendingReport } from "./types";

export default function App() {
  const [activeView, setActiveView] = useState<ViewId>("trending");
  const [report, setReport] = useState<TrendingReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [showLogs, setShowLogs] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  function handleRequestShowLogs() {
    setShowLogs(true);
  }

  async function handlePipeline() {
    setLoading(true);
    setMessage("");
    try {
      const result = await runFullPipeline();
      setMessage(`抓取 ${result.collected} 篇，处理 ${result.processed} 篇，打标 ${result.tagged} 条`);
      const trending = await getTrending();
      setReport(trending);
      setActiveView("trending");
    } catch {
      setMessage("Pipeline 执行失败，请检查配置。");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    try {
      const trending = await getTrending();
      setReport(trending);
    } catch {
      setMessage("获取 Trending 失败");
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <h1>Sailor</h1>
          <p>智能信息采集与管理</p>
        </div>
        <div className="hero-actions">
          <button onClick={() => setShowLogs(!showLogs)} className={showLogs ? "active" : ""}>
            📋 日志
          </button>
        </div>
      </header>

      {message && <p className="message">{message}</p>}

      <div className="app-body">
        <NavBar active={activeView} onChange={setActiveView} onSettingsClick={() => setShowSettings(true)} />
        <main className="main-area">
          {activeView === "trending" && <TrendingPage report={report} loading={loading} />}
          {activeView === "tags" && <TagPage onNavigateToTrending={() => setActiveView("trending")} />}
          {activeView === "kb" && <KBPage />}
          {activeView === "feeds" && <FeedPage onRequestShowLogs={handleRequestShowLogs} />}
          {activeView === "sniffer" && <SnifferPage />}
        </main>
      </div>

      <LogPanel isOpen={showLogs} onClose={() => setShowLogs(false)} />
      <LLMSettingsModal open={showSettings} onClose={() => setShowSettings(false)} />
    </div>
  );
}
