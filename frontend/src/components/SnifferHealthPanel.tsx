import { useEffect, useState } from "react";
import type { ChannelHealth } from "../types";
import { getChannelHealth } from "../api";

export default function SnifferHealthPanel() {
  const [channels, setChannels] = useState<ChannelHealth[]>([]);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try { setChannels(await getChannelHealth()); } catch { /* ignore */ }
    setLoading(false);
  }

  useEffect(() => { refresh(); }, []);

  const statusColor = (s: string) =>
    s === "ok" ? "var(--accent-1)" : s === "warn" ? "#f59e0b" : "var(--danger)";

  return (
    <div className="sniffer-health-panel">
      <div className="sniffer-health-header">
        <h4>渠道状态</h4>
        <button className="sniffer-action-btn" onClick={refresh} disabled={loading}>
          {loading ? "检测中..." : "刷新"}
        </button>
      </div>
      <div className="sniffer-health-list">
        {channels.map((ch) => (
          <div key={ch.channel_id} className="sniffer-health-item">
            <span className="sniffer-health-icon">{ch.icon}</span>
            <span className="sniffer-health-name">{ch.display_name}</span>
            <span
              className="sniffer-health-dot"
              style={{ background: statusColor(ch.status) }}
              title={ch.message || ch.status}
            />
            {ch.latency_ms != null && (
              <span className="sniffer-health-latency">{ch.latency_ms}ms</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
