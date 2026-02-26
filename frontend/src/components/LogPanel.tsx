import { useEffect, useRef, useState } from "react";
import { createLogStream, getRecentLogs, type LogEntry } from "../api";

interface LogPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function LogPanel({ isOpen, onClose }: LogPanelProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [debugInfo, setDebugInfo] = useState<string>("");
  const logsEndRef = useRef<HTMLDivElement>(null);

  const handleRefresh = async () => {
    try {
      setDebugInfo("Refreshing logs...");
      const recent = await getRecentLogs(80);
      setLogs(recent);
      setDebugInfo(`Loaded ${recent.length} logs at ${new Date().toLocaleTimeString()}`);
    } catch (e) {
      setError(`Refresh failed: ${e}`);
    }
  };

  useEffect(() => {
    if (!isOpen) return;

    let disposed = false;
    let eventSource: EventSource | null = null;

    const bootstrap = async () => {
      try {
        const recent = await getRecentLogs(80);
        if (!disposed) {
          setLogs(recent);
        }
      } catch {
        if (!disposed) {
          setLogs([]);
        }
      }

      if (disposed) return;

      eventSource = createLogStream();
      setConnected(true);

      eventSource.onmessage = (event) => {
        console.log("[LogPanel] Received:", event.data);
        const parsed = parseLogLine(event.data);
        if (!parsed) {
          console.log("[LogPanel] Parse failed for:", event.data);
          return;
        }
        setLogs((prev) => [...prev.slice(-99), parsed]);
      };

      eventSource.onerror = () => {
        console.log("[LogPanel] SSE error");
        setConnected(false);
        eventSource?.close();
      };
    };

    bootstrap();

    return () => {
      disposed = true;
      eventSource?.close();
      setConnected(false);
    };
  }, [isOpen]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  if (!isOpen) return null;

  return (
    <div className="log-panel">
      <div className="log-panel-header">
        <span>📋 日志 {connected ? "🟢" : "🔴"}</span>
        <button onClick={handleRefresh} title="刷新">↻</button>
        <button onClick={onClose}>✕</button>
      </div>
      {error && <div className="log-error">⚠️ {error}</div>}
      {debugInfo && <div className="log-debug">ℹ️ {debugInfo}</div>}
      <div className="log-panel-content">
        {logs.length === 0 ? (
          <div className="log-empty">暂无日志</div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className={`log-entry log-${log.level.toLowerCase()}`}>
              <span className="log-time">{log.time}</span>
              <span className={`log-level log-level-${log.level.toLowerCase()}`}>{log.level}</span>
              <span className="log-message">{log.message}</span>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
}

function parseLogLine(line: string): LogEntry | null {
  if (!line || line.startsWith(":")) {
    return null;
  }

  const parts = line.split(" | ");
  if (parts.length < 3) {
    return null;
  }

  const time = parts[0]?.trim();
  const level = parts[1]?.trim();
  const message = parts.slice(2).join(" | ").trim();

  if (!time || !level || !message) {
    return null;
  }

  return { time, level, message };
}
