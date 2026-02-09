import type { MainFlowTask } from "../types";

type Props = {
  tasks: MainFlowTask[];
};

export default function TaskPanel({ tasks }: Props) {
  return (
    <aside className="task-panel">
      <h2>Main User Flow Tasks</h2>
      <p>Auto-generated from stage 4 flow: scan -&gt; review -&gt; decide.</p>
      {tasks.length === 0 ? (
        <div className="empty">No pending inbox tasks.</div>
      ) : (
        <ul>
          {tasks.map((task) => (
            <li key={task.task_id}>
              <strong>{task.title}</strong>
              <span>{task.description}</span>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
