import { useState } from "react";

import NavBar from "./components/NavBar";
import LogPanel from "./components/LogPanel";
import LLMSettingsModal from "./components/LLMSettingsModal";
import type { ViewId } from "./components/NavBar";
import FeedPage from "./pages/FeedPage";
import KBPage from "./pages/KBPage";
import DiscoverPage from "./pages/DiscoverPage";
import FollowPage from "./pages/FollowPage";

export default function App() {
  const [activeView, setActiveView] = useState<ViewId>("discover");
  const [message, setMessage] = useState("");
  const [showLogs, setShowLogs] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  function handleRequestShowLogs() {
    setShowLogs(true);
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
          {activeView === "discover" && <DiscoverPage />}
          {activeView === "feeds" && <FeedPage onRequestShowLogs={handleRequestShowLogs} />}
          {activeView === "kb" && <KBPage />}
          {activeView === "follow" && <FollowPage />}
        </main>
      </div>

      <LogPanel isOpen={showLogs} onClose={() => setShowLogs(false)} />
      <LLMSettingsModal open={showSettings} onClose={() => setShowSettings(false)} />
    </div>
  );
}
