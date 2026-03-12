import { JobCancelledError, JobFailedError, JobTimeoutError } from "./api";

export type ToastFn = {
  success: (msg: string) => void;
  error: (msg: string) => void;
  info: (msg: string) => void;
};

export function formatJobError(e: unknown, fallbackMsg: string): string {
  if (e instanceof JobTimeoutError) {
    return `任务仍在后台运行（job_id=${e.jobId}，status=${e.lastStatus}）`;
  }
  if (e instanceof JobCancelledError) {
    return `任务已取消（job_id=${e.jobId}）`;
  }
  if (e instanceof JobFailedError) {
    return `${fallbackMsg}（job_id=${e.jobId}）：${e.errorMessage}`;
  }
  if (e instanceof Error) {
    return `${fallbackMsg}：${e.message}`;
  }
  return fallbackMsg;
}

export function showJobError(toast: ToastFn, e: unknown, fallbackMsg: string): void {
  if (e instanceof JobTimeoutError) {
    toast.info(`任务仍在后台运行 (job: ${e.jobId})，请稍后查看`);
    return;
  }
  if (e instanceof JobCancelledError) {
    toast.info(`任务已取消 (job: ${e.jobId})`);
    return;
  }
  if (e instanceof JobFailedError) {
    toast.error(`${fallbackMsg} (job: ${e.jobId})：${e.errorMessage}`);
    return;
  }
  toast.error(formatJobError(e, fallbackMsg));
}

