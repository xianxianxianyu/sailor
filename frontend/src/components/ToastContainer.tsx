import type { ToastItem } from "../hooks/useToast";

type Props = {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
};

export default function ToastContainer({ toasts, onDismiss }: Props) {
  if (toasts.length === 0) return null;

  return (
    <div className="toast-container" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast-item toast-${t.level}`}>
          <span className="toast-message">{t.message}</span>
          <button className="toast-close" onClick={() => onDismiss(t.id)} aria-label="关闭">✕</button>
        </div>
      ))}
    </div>
  );
}
