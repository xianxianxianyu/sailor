import type { Resource } from "../types";

type Props = {
  resource: Resource;
  archivedCount: number;
  onOpen: (resource: Resource) => void;
  onAdd: (resource: Resource) => void;
};

export default function ResourceCard({ resource, archivedCount, onOpen, onAdd }: Props) {
  return (
    <article className="resource-card">
      <header>
        <button className="link-button" onClick={() => onOpen(resource)}>
          {resource.title}
        </button>
        <button className="plus-button" onClick={() => onAdd(resource)} aria-label="Add to knowledge base">
          +
        </button>
      </header>
      <div className="topic-row">
        {resource.topics.map((topic) => (
          <span key={topic} className="topic-chip">
            {topic}
          </span>
        ))}
      </div>
      <p>{resource.summary}</p>
      <footer>
        <a href={resource.original_url} target="_blank" rel="noreferrer">
          Open source
        </a>
        {archivedCount > 0 ? <span className="archived-flag">Archived x{archivedCount}</span> : null}
      </footer>
    </article>
  );
}
