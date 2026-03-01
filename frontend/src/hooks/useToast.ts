import { useState, useCallback, useRef } from "react";

export type ToastLevel = "success" | "error" | "info";

export type ToastItem = {
  id: number;
  level: ToastLevel;
  message: string;
};

let nextId = 1;

export default function useToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) { clearTimeout(timer); timers.current.delete(id); }
  }, []);

  const push = useCallback((level: ToastLevel, message: string) => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, level, message }]);
    const timer = setTimeout(() => dismiss(id), 3000);
    timers.current.set(id, timer);
  }, [dismiss]);

  const toast = {
    success: (msg: string) => push("success", msg),
    error: (msg: string) => push("error", msg),
    info: (msg: string) => push("info", msg),
  };

  return { toasts, toast, dismiss };
}
