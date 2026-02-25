import { useEffect, useRef, useState } from "react";
import { createLogStream, type LogEntry } from "../api";

interface LogPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function LogPanel({ isOpen, onClose }: LogPanelProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const eventSource = createLogStream();
    setConnected(true);

    eventSource.onmessage = (event) => {
      if (event.data.startsWith("data: :")) return; // heartbeat
      
      const data = event.data.replace("data: ", "");
      const [time, level, message] = data.split(" | ");
      
      if (time && level && message) {
        setLogs((prev) => [...prev.slice(-99), { time, level, message }]);
      }
    };

    eventSource.onerror = () => {
      setConnected(false);
      eventSource.close();
    };

    return () => {
      eventSource.close();
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
        <button onClick={onClose}>✕</button>
      </div>
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
