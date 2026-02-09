import { useEffect, useMemo, useState } from "react";

import {
  addToKnowledgeBase,
  getKnowledgeBases,
  getMainFlowTasks,
  getResourceKnowledgeBases,
  getResources,
  runIngestion,
} from "./api";
import KBPickerModal from "./components/KBPickerModal";
import ResourceCard from "./components/ResourceCard";
import TaskPanel from "./components/TaskPanel";
import type { KnowledgeBase, MainFlowTask, Resource } from "./types";

function uniqueTopics(resources: Resource[]): string[] {
  const values = new Set<string>();
  resources.forEach((item) => item.topics.forEach((topic) => values.add(topic)));
  return [...values].sort((a, b) => a.localeCompare(b));
}

export default function App() {
  const [resources, setResources] = useState<Resource[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [tasks, setTasks] = useState<MainFlowTask[]>([]);
  const [resourceKbMap, setResourceKbMap] = useState<Record<string, KnowledgeBase[]>>({});
  const [selectedTopic, setSelectedTopic] = useState<string>("");
  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);
  const [pickerResource, setPickerResource] = useState<Resource | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string>("");

  const topics = useMemo(() => uniqueTopics(resources), [resources]);

  async function loadAll(topic?: string) {
    const [loadedResources, loadedKbs, loadedTasks] = await Promise.all([
      getResources(topic),
      getKnowledgeBases(),
      getMainFlowTasks(),
    ]);
    setResources(loadedResources);
    setKnowledgeBases(loadedKbs);
    setTasks(loadedTasks);

    const kbPairs = await Promise.all(
      loadedResources.map(async (resource) => {
        const kbs = await getResourceKnowledgeBases(resource.resource_id);
        return [resource.resource_id, kbs] as const;
      })
    );
    setResourceKbMap(Object.fromEntries(kbPairs));
  }

  useEffect(() => {
    runIngestion()
      .then(() => loadAll())
      .catch(() => setMessage("Initial ingestion failed. Please sync manually."));
  }, []);

  async function onSync() {
    try {
      setBusy(true);
      const result = await runIngestion();
      await loadAll(selectedTopic || undefined);
      setMessage(`Synced ${result.processed_count} resources.`);
    } finally {
      setBusy(false);
    }
  }

  async function onTopicChange(topic: string) {
    setSelectedTopic(topic);
    await loadAll(topic || undefined);
  }

  async function onConfirmAdd(kbId: string) {
    if (!pickerResource) {
      return;
    }

    setBusy(true);
    try {
      await addToKnowledgeBase(kbId, pickerResource.resource_id);
      const kbs = await getResourceKnowledgeBases(pickerResource.resource_id);
      setResourceKbMap((prev) => ({ ...prev, [pickerResource.resource_id]: kbs }));
      setMessage(`Added to ${knowledgeBases.find((kb) => kb.kb_id === kbId)?.name ?? "knowledge base"}.`);
      setPickerResource(null);
      await loadAll(selectedTopic || undefined);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <h1>Sailor Inbox</h1>
          <p>Scan high-signal resources, review details, and archive into your knowledge bases.</p>
        </div>
        <div className="hero-actions">
          <select value={selectedTopic} onChange={(event) => onTopicChange(event.target.value)}>
            <option value="">All Topics</option>
            {topics.map((topic) => (
              <option key={topic} value={topic}>
                {topic}
              </option>
            ))}
          </select>
          <button onClick={onSync} disabled={busy}>
            {busy ? "Syncing..." : "Sync Ingestion"}
          </button>
        </div>
      </header>

      {message ? <p className="message">{message}</p> : null}

      <main className="layout-grid">
        <section className="feed-section">
          <h2>Resource Feed</h2>
          {resources.length === 0 ? <div className="empty">No inbox resources.</div> : null}
          <div className="feed-grid">
            {resources.map((resource) => (
              <ResourceCard
                key={resource.resource_id}
                resource={resource}
                archivedCount={resourceKbMap[resource.resource_id]?.length ?? 0}
                onOpen={setSelectedResource}
                onAdd={setPickerResource}
              />
            ))}
          </div>
        </section>

        <section className="detail-panel">
          <h2>Resource Detail</h2>
          {selectedResource ? (
            <article>
              <h3>{selectedResource.title}</h3>
              <div className="topic-row">
                {selectedResource.topics.map((topic) => (
                  <span key={topic} className="topic-chip">
                    {topic}
                  </span>
                ))}
              </div>
              <p>{selectedResource.text || selectedResource.summary}</p>
              <div className="detail-actions">
                <a href={selectedResource.original_url} target="_blank" rel="noreferrer">
                  Open original article
                </a>
                <button onClick={() => setPickerResource(selectedResource)}>+ Add to KB</button>
              </div>
            </article>
          ) : (
            <div className="empty">Pick a resource from the feed to review details.</div>
          )}
        </section>

        <TaskPanel tasks={tasks} />
      </main>

      <KBPickerModal
        open={Boolean(pickerResource)}
        resourceTitle={pickerResource?.title ?? ""}
        knowledgeBases={knowledgeBases}
        knownKbIds={pickerResource ? (resourceKbMap[pickerResource.resource_id] ?? []).map((kb) => kb.kb_id) : []}
        submitting={busy}
        onCancel={() => setPickerResource(null)}
        onConfirm={onConfirmAdd}
      />
    </div>
  );
}
