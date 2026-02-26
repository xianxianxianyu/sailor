import React from "react";
import type { RSSFeed, SourceRecord } from "../types";

export type AnySource = (SourceRecord & { sourceKind: "unified" }) | (RSSFeed & { sourceKind: "rss" });

interface SourceListProps {
  sources: AnySource[];
  selectedId: string | null;
  onSelect: (source: AnySource) => void;
}

interface GroupedSources {
  [key: string]: AnySource[];
}

export function getSourceGroups(sources: AnySource[]): GroupedSources {
  return sources.reduce((acc, source) => {
    let groupKey: string;
    if (source.sourceKind === "unified") {
      const domain = (source as SourceRecord).config?.content_domain as string | undefined;
      groupKey = domain || getInferredGroup((source as SourceRecord).source_type);
    } else {
      groupKey = "rss";
    }

    if (!acc[groupKey]) acc[groupKey] = [];
    acc[groupKey].push(source);
    return acc;
  }, {} as GroupedSources);
}

function getInferredGroup(sourceType: string): string {
  const typeToGroup: Record<string, string> = {
    academic: "academic",
    academic_api: "academic",
    rss: "rss",
    atom: "rss",
    jsonfeed: "rss",
    api: "tech_blog",
    api_json: "tech_blog",
    api_xml: "tech_blog",
    web_page: "tech_blog",
    site_map: "tech_blog",
    opml: "personal_blog",
    jsonl: "personal_blog",
    manual_file: "personal_blog",
  };
  return typeToGroup[sourceType] || "generic";
}

export function getGroupIcon(group: string): string {
  const icons: Record<string, string> = {
    academic: "📚",
    tech_blog: "💻",
    personal_blog: "📝",
    news: "📡",
    rss: "📡",
    generic: "🔗",
  };
  return icons[group] || "🔗";
}

export function getGroupName(group: string): string {
  const names: Record<string, string> = {
    academic: "学术论文",
    tech_blog: "技术博客",
    personal_blog: "个人博客",
    news: "聚合资讯",
    rss: "RSS 订阅",
    generic: "通用",
  };
  return names[group] || group;
}

export function getSourceTypeIcon(sourceType: string): string {
  const icons: Record<string, string> = {
    rss: "📡",
    atom: "📡",
    jsonfeed: "📡",
    academic_api: "📚",
    api: "🔌",
    api_json: "📄",
    api_xml: "📄",
    web_page: "🌐",
    site_map: "🗺️",
    opml: "📋",
    jsonl: "📋",
    manual_file: "📁",
  };
  return icons[sourceType] || "🔗";
}

export function getSourceName(source: AnySource): string {
  if (source.sourceKind === "rss") {
    return (source as RSSFeed).name;
  }
  return (source as SourceRecord).name;
}

export function getSourceStatus(source: AnySource): "enabled" | "disabled" | "error" {
  if (source.sourceKind === "rss") {
    const feed = source as RSSFeed;
    if (!feed.enabled) return "disabled";
    if (feed.error_count > 0) return "error";
    return "enabled";
  }
  const rec = source as SourceRecord;
  if (!rec.enabled) return "disabled";
  if (rec.error_count > 0) return "error";
  return "enabled";
}

export function formatLastRun(lastRunAt: string | null): string {
  if (!lastRunAt) return "从未运行";
  const date = new Date(lastRunAt);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return "刚刚";
  if (diffMins < 60) return `${diffMins} 分钟前`;
  if (diffHours < 24) return `${diffHours} 小时前`;
  if (diffDays < 7) return `${diffDays} 天前`;
  return date.toLocaleDateString("zh-CN");
}

export default function SourceList({ sources, selectedId, onSelect }: SourceListProps) {
  const [searchText, setSearchText] = React.useState("");
  const [collapsedGroups, setCollapsedGroups] = React.useState<Set<string>>(new Set());

  const filteredSources = searchText
    ? sources.filter((s) => getSourceName(s).toLowerCase().includes(searchText.toLowerCase()))
    : sources;

  const groupedSources = getSourceGroups(filteredSources);
  const sortedGroups = Object.keys(groupedSources).sort((a, b) => {
    const order = ["academic", "tech_blog", "personal_blog", "news", "rss", "generic"];
    const idxA = order.indexOf(a);
    const idxB = order.indexOf(b);
    if (idxA !== idxB) return idxA - idxB;
    return a.localeCompare(b);
  });

  function toggleGroup(group: string) {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(group)) {
        next.delete(group);
      } else {
        next.add(group);
      }
      return next;
    });
  }

  function getUniqueId(source: AnySource): string {
    if (source.sourceKind === "rss") {
      return `rss-${(source as RSSFeed).feed_id}`;
    }
    return `unified-${(source as SourceRecord).source_id}`;
  }

  return (
    <div className="source-list">
      <div className="source-list-search">
        <input
          type="text"
          placeholder="搜索源..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          className="source-search-input"
        />
      </div>

      <div className="source-list-content">
        {sortedGroups.length === 0 ? (
          <div className="source-list-empty">
            {searchText ? "没有匹配的源" : "暂无订阅源"}
          </div>
        ) : (
          sortedGroups.map((group) => {
            const isCollapsed = collapsedGroups.has(group);
            const groupSources = groupedSources[group];

            return (
              <div key={group} className="source-group-wrapper">
                <button
                  className="source-group-header"
                  onClick={() => toggleGroup(group)}
                >
                  <span className="source-group-toggle">{isCollapsed ? "▶" : "▼"}</span>
                  <span className="source-group-icon">{getGroupIcon(group)}</span>
                  <span className="source-group-name">{getGroupName(group)}</span>
                  <span className="source-group-count">({groupSources.length})</span>
                </button>

                {!isCollapsed && (
                  <div className="source-group-items">
                    {groupSources.map((source) => {
                      const uniqueId = getUniqueId(source);
                      const isSelected = selectedId === uniqueId;
                      const status = getSourceStatus(source);
                      const sourceType = source.sourceKind === "rss" ? "rss" : (source as SourceRecord).source_type;

                      return (
                        <button
                          key={uniqueId}
                          className={`source-list-item ${isSelected ? "source-list-item-selected" : ""}`}
                          onClick={() => onSelect(source)}
                        >
                          <span className="source-item-icon">{getSourceTypeIcon(sourceType)}</span>
                          <span className="source-item-name">{getSourceName(source)}</span>
                          <span className={`source-item-status source-item-status-${status}`}>
                            {status === "enabled" ? "●" : status === "disabled" ? "○" : "⚠"}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}