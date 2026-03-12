import { useState, useMemo } from "react";
import {
  snifferSearch,
  JobCancelledError,
  JobFailedError,
  JobTimeoutError,
  deepAnalyze,
  compareResults,
  saveToKB,
  convertToSource,
  getKnowledgeBases,
} from "../api";
import { showJobError } from "../jobErrors";
import type {
  CompareSummary,
  KnowledgeBase,
  ResourceAnalysis,
  SearchResponse,
  SniffResult,
} from "../types";

export type InspectorTarget =
  | { kind: "summary" }
  | { kind: "detail"; resultId: string }
  | { kind: "compare" };

export type SnifferWorkspace = ReturnType<typeof useSnifferWorkspace>;

type ToastFn = {
  success: (msg: string) => void;
  error: (msg: string) => void;
  info: (msg: string) => void;
};

export default function useSnifferWorkspace(toast?: ToastFn) {
  // --- core search state ---
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // --- selection ---
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // --- compare ---
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareSummary, setCompareSummary] = useState<CompareSummary | null>(null);

  // --- deep analyze ---
  const [analysisResult, setAnalysisResult] = useState<ResourceAnalysis | null>(null);
  const [analysisTargetId, setAnalysisTargetId] = useState<string | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // --- KB picker ---
  const [kbPickerOpen, setKbPickerOpen] = useState(false);
  const [kbPickerResultId, setKbPickerResultId] = useState("");
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [kbSubmitting, setKbSubmitting] = useState(false);

  // --- inspector target auto-derivation ---
  const inspectorTarget = useMemo<InspectorTarget | null>(() => {
    if (!response) return null;
    if (selectedIds.size === 0) return { kind: "summary" };
    if (selectedIds.size === 1) {
      const [id] = selectedIds;
      return { kind: "detail", resultId: id };
    }
    return { kind: "compare" };
  }, [response, selectedIds]);

  // --- handlers ---

  async function handleSearch(query: {
    keyword: string; channels: string[]; time_range: string;
    sort_by: string; max_results_per_channel: number;
  }) {
    setLoading(true); setError(""); setSelectedIds(new Set());
    setAnalysisResult(null); setAnalysisTargetId(null);
    setCompareSummary(null);
    try { setResponse(await snifferSearch(query)); }
    catch (e: unknown) {
      if (e instanceof JobTimeoutError) {
        setError(`搜索仍在后台运行（job_id=${e.jobId}，status=${e.lastStatus}）`);
      } else if (e instanceof JobCancelledError) {
        setError(`搜索已取消（job_id=${e.jobId}）`);
      } else if (e instanceof JobFailedError) {
        setError(`搜索失败：${e.errorMessage}（job_id=${e.jobId}）`);
      } else {
        setError("搜索失败，请检查网络或稍后重试。");
      }
    }
    finally { setLoading(false); }
  }

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
    // clear stale inspector data when selection changes
    setAnalysisResult(null);
    setAnalysisTargetId(null);
    setCompareSummary(null);
  }

  function clearSelection() {
    setSelectedIds(new Set());
    setAnalysisResult(null);
    setAnalysisTargetId(null);
    setCompareSummary(null);
  }

  async function handleCompare() {
    if (selectedIds.size < 2) return;
    setCompareLoading(true); setCompareSummary(null);
    try { setCompareSummary(await compareResults([...selectedIds])); }
    catch (e: unknown) { if (toast) showJobError(toast, e, "对比分析失败"); }
    setCompareLoading(false);
  }

  async function handleDeepAnalyze(resultId: string) {
    setAnalysisLoading(true); setAnalysisTargetId(resultId); setAnalysisResult(null);
    try { setAnalysisResult(await deepAnalyze(resultId)); }
    catch (e: unknown) { if (toast) showJobError(toast, e, "分析失败"); }
    setAnalysisLoading(false);
  }

  async function handleSaveToKB(resultId: string) {
    setKbPickerResultId(resultId);
    try { setKbs(await getKnowledgeBases()); } catch { toast?.error("获取知识库列表失败"); }
    setKbPickerOpen(true);
  }

  async function handleKBConfirm(kbId: string) {
    setKbSubmitting(true);
    try { await saveToKB(kbPickerResultId, kbId); toast?.success("已收藏到知识库"); } catch (e: unknown) { if (toast) showJobError(toast, e, "收藏失败"); }
    setKbSubmitting(false); setKbPickerOpen(false);
  }

  async function handleConvertSource(resultId: string) {
    try { await convertToSource(resultId); toast?.success("已转为订阅源"); } catch (e: unknown) { if (toast) showJobError(toast, e, "转订阅失败"); }
  }

  function handlePackRun(res: SearchResponse) {
    setResponse(res);
    setSelectedIds(new Set());
    setAnalysisResult(null); setAnalysisTargetId(null);
    setCompareSummary(null);
  }

  // --- derived ---
  const results: SniffResult[] = response?.results ?? [];
  const kbPickerTitle = useMemo(() => {
    if (!kbPickerResultId) return "";
    const found = results.find((r) => r.result_id === kbPickerResultId);
    return found?.title ?? kbPickerResultId;
  }, [results, kbPickerResultId]);

  return {
    // state
    response,
    loading,
    error,
    selectedIds,
    compareLoading,
    compareSummary,
    analysisResult,
    analysisTargetId,
    analysisLoading,
    kbPickerOpen,
    kbPickerResultId,
    kbPickerTitle,
    kbs,
    kbSubmitting,
    inspectorTarget,
    results,
    // actions
    handleSearch,
    toggleSelect,
    clearSelection,
    handleCompare,
    handleDeepAnalyze,
    handleSaveToKB,
    handleKBConfirm,
    handleConvertSource,
    handlePackRun,
    setKbPickerOpen,
  };
}


