import { useEffect, useState } from "react";
import type { SearchResponse, SnifferPack } from "../types";
import {
  getSnifferPacks,
  deleteSnifferPack,
  runSnifferPack,
  importSnifferPack,
  exportSnifferPack,
  updatePackSchedule,
} from "../api";

type Props = {
  onPackRun?: (results: SearchResponse) => void;
  onPackRunError?: (error: unknown) => void;
};

const SCHEDULE_OPTIONS = [
  { label: "关闭", value: "" },
  { label: "每小时", value: "every_1h" },
  { label: "每6小时", value: "every_6h" },
  { label: "每12小时", value: "every_12h" },
  { label: "每天", value: "every_24h" },
];

export default function SnifferPackPanel({ onPackRun, onPackRunError }: Props) {
  const [packs, setPacks] = useState<SnifferPack[]>([]);
  const [busy, setBusy] = useState("");
  const [importJson, setImportJson] = useState("");
  const [showImport, setShowImport] = useState(false);

  useEffect(() => { loadPacks(); }, []);

  async function loadPacks() {
    try { setPacks(await getSnifferPacks()); } catch { }
  }

  async function handleRun(packId: string) {
    setBusy(packId);
    try {
      const res = await runSnifferPack(packId);
      onPackRun?.(res);
    } catch (e: unknown) {
      onPackRunError?.(e);
    } finally {
      setBusy("");
    }
  }

  async function handleDelete(packId: string) {
    await deleteSnifferPack(packId);
    loadPacks();
  }

  async function handleExport(packId: string) {
    const data = await exportSnifferPack(packId);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `pack-${packId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleImport() {
    try {
      const data = JSON.parse(importJson);
      await importSnifferPack(data);
      setImportJson("");
      setShowImport(false);
      loadPacks();
    } catch { }
  }

  async function handleSchedule(packId: string, cron: string) {
    await updatePackSchedule(packId, cron || null);
    loadPacks();
  }

  return (
    <div className="sniffer-pack-panel">
      <div className="sniffer-pack-header">
        <h3>搜索包</h3>
        <button className="sniffer-action-btn" onClick={() => setShowImport(!showImport)}>导入</button>
      </div>

      {showImport && (
        <div className="sniffer-pack-import">
          <textarea
            value={importJson}
            onChange={(e) => setImportJson(e.target.value)}
            placeholder='粘贴 JSON...'
            rows={4}
          />
          <button className="sniffer-action-btn" onClick={handleImport}>确认导入</button>
        </div>
      )}

      {packs.length === 0 && <p className="sniffer-pack-empty">暂无搜索包</p>}

      {packs.map((p) => (
        <div key={p.pack_id} className="sniffer-pack-card">
          <div className="sniffer-pack-info">
            <strong>{p.name}</strong>
            {p.description && <small>{p.description}</small>}
          </div>
          <div className="sniffer-pack-schedule">
            <select
              value={p.schedule_cron || ""}
              onChange={(e) => handleSchedule(p.pack_id, e.target.value)}
            >
              {SCHEDULE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div className="sniffer-pack-actions">
            <button onClick={() => handleRun(p.pack_id)} disabled={busy === p.pack_id}>
              {busy === p.pack_id ? "运行中..." : "运行"}
            </button>
            <button onClick={() => handleExport(p.pack_id)}>导出</button>
            <button onClick={() => handleDelete(p.pack_id)}>删除</button>
          </div>
        </div>
      ))}
    </div>
  );
}
