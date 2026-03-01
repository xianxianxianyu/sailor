import { useState } from "react";
import SnifferPackPanel from "./SnifferPackPanel";
import SnifferHealthPanel from "./SnifferHealthPanel";

type Props = {
  open: boolean;
  onClose: () => void;
  onPackRun: (res: unknown) => void;
};

export default function SnifferToolsDrawer({ open, onClose, onPackRun }: Props) {
  const [tab, setTab] = useState<"packs" | "health">("packs");

  if (!open) return null;

  return (
    <div className="sniffer-tools-backdrop" onClick={onClose}>
      <aside className="sniffer-tools-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="sniffer-tools-header">
          <div className="sniffer-tools-tabs">
            <button className={tab === "packs" ? "active" : ""} onClick={() => setTab("packs")}>嗅探包</button>
            <button className={tab === "health" ? "active" : ""} onClick={() => setTab("health")}>渠道状态</button>
          </div>
          <button className="sniffer-tools-close" onClick={onClose} aria-label="关闭">✕</button>
        </div>
        <div className="sniffer-tools-body">
          {tab === "packs" && <SnifferPackPanel onPackRun={onPackRun} />}
          {tab === "health" && <SnifferHealthPanel />}
        </div>
      </aside>
    </div>
  );
}
