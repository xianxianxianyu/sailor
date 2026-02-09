import { useMemo, useState } from "react";

import type { KnowledgeBase } from "../types";

type Props = {
  open: boolean;
  resourceTitle: string;
  knownKbIds: string[];
  knowledgeBases: KnowledgeBase[];
  submitting: boolean;
  onCancel: () => void;
  onConfirm: (kbId: string) => void;
};

export default function KBPickerModal({
  open,
  resourceTitle,
  knownKbIds,
  knowledgeBases,
  submitting,
  onCancel,
  onConfirm,
}: Props) {
  const [selectedKbId, setSelectedKbId] = useState<string>("");

  const sorted = useMemo(() => {
    const known = new Set(knownKbIds);
    return [...knowledgeBases].sort((a, b) => {
      const aAdded = known.has(a.kb_id);
      const bAdded = known.has(b.kb_id);
      if (aAdded === bAdded) {
        return a.name.localeCompare(b.name);
      }
      return aAdded ? 1 : -1;
    });
  }, [knowledgeBases, knownKbIds]);

  if (!open) {
    return null;
  }

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <h3>Add to Knowledge Base</h3>
        <p className="modal-subtitle">{resourceTitle}</p>

        <ul className="kb-list">
          {sorted.map((kb) => {
            const alreadyAdded = knownKbIds.includes(kb.kb_id);
            return (
              <li key={kb.kb_id}>
                <label>
                  <input
                    type="radio"
                    name="knowledge-base"
                    value={kb.kb_id}
                    disabled={alreadyAdded || submitting}
                    checked={selectedKbId === kb.kb_id}
                    onChange={() => setSelectedKbId(kb.kb_id)}
                  />
                  <span>{kb.name}</span>
                  {alreadyAdded ? <em>already added</em> : null}
                </label>
              </li>
            );
          })}
        </ul>

        <div className="modal-actions">
          <button onClick={onCancel} disabled={submitting}>
            Cancel
          </button>
          <button
            className="primary"
            onClick={() => selectedKbId && onConfirm(selectedKbId)}
            disabled={!selectedKbId || submitting}
          >
            {submitting ? "Adding..." : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}
