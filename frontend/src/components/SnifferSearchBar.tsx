import { useState, useEffect } from "react";
import { getSnifferChannels } from "../api";
import type { ChannelInfo } from "../types";

type Props = {
  onSearch: (query: {
    keyword: string;
    channels: string[];
    time_range: string;
    sort_by: string;
    max_results_per_channel: number;
  }) => void;
  loading: boolean;
  onSavePack?: (query: {
    keyword: string;
    channels: string[];
    time_range: string;
    sort_by: string;
    max_results_per_channel: number;
  }) => void;
};

export default function SnifferSearchBar({ onSearch, loading, onSavePack }: Props) {
  const [keyword, setKeyword] = useState("");
  const [channels, setChannels] = useState<ChannelInfo[]>([]);
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [timeRange, setTimeRange] = useState("all");
  const [sortBy, setSortBy] = useState("relevance");

  useEffect(() => {
    getSnifferChannels().then(setChannels).catch(() => {});
  }, []);

  function toggleChannel(id: string) {
    setSelectedChannels((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!keyword.trim()) return;
    onSearch({
      keyword: keyword.trim(),
      channels: selectedChannels,
      time_range: timeRange,
      sort_by: sortBy,
      max_results_per_channel: 10,
    });
  }

  return (
    <form className="sniffer-search-bar" onSubmit={handleSubmit}>
      <div className="sniffer-input-row">
        <input
          type="text"
          className="sniffer-keyword-input"
          placeholder="输入关键词搜索..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          aria-label="搜索关键词"
        />
        <button type="submit" className="sniffer-search-btn" disabled={loading || !keyword.trim()}>
          {loading ? "搜索中..." : "搜索"}
        </button>
        {onSavePack && keyword.trim() && (
          <button
            type="button"
            className="sniffer-action-btn"
            onClick={() => onSavePack({
              keyword: keyword.trim(),
              channels: selectedChannels,
              time_range: timeRange,
              sort_by: sortBy,
              max_results_per_channel: 10,
            })}
          >
            保存为嗅探包
          </button>
        )}
      </div>

      <div className="sniffer-filters">
        <div className="sniffer-channels">
          {channels.map((ch) => (
            <label key={ch.channel_id} className="sniffer-channel-label">
              <input
                type="checkbox"
                checked={selectedChannels.includes(ch.channel_id)}
                onChange={() => toggleChannel(ch.channel_id)}
              />
              <span className="sniffer-channel-icon">{ch.icon}</span>
              {ch.display_name}
              <span className={`sniffer-channel-status sniffer-status-${ch.status}`} title={ch.message} />
            </label>
          ))}
        </div>

        <div className="sniffer-dropdowns">
          <select value={timeRange} onChange={(e) => setTimeRange(e.target.value)} aria-label="时间范围">
            <option value="all">全部时间</option>
            <option value="24h">24 小时</option>
            <option value="7d">7 天</option>
            <option value="30d">30 天</option>
          </select>

          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} aria-label="排序方式">
            <option value="relevance">相关度</option>
            <option value="time">时间</option>
            <option value="popularity">热度</option>
          </select>
        </div>
      </div>
    </form>
  );
}
