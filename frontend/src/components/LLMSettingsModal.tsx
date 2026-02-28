import { useEffect, useState } from "react";

import { getLLMSettings, testLLMConnection, updateLLMSettings } from "../api";
import type { LLMSettings } from "../types";

type Props = {
  open: boolean;
  onClose: () => void;
};

type Provider = "deepseek" | "openai" | "custom";

const PROVIDER_PRESETS: Record<Provider, { label: string; baseUrl: string; models: string[] }> = {
  deepseek: {
    label: "DeepSeek",
    baseUrl: "https://api.deepseek.com/v1",
    models: ["deepseek-chat", "deepseek-reasoner"],
  },
  openai: {
    label: "OpenAI",
    baseUrl: "https://api.openai.com/v1",
    models: ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "o1-mini"],
  },
  custom: {
    label: "自定义",
    baseUrl: "",
    models: [],
  },
};

export default function LLMSettingsModal({ open, onClose }: Props) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [error, setError] = useState("");

  const [provider, setProvider] = useState<Provider>("deepseek");
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [baseUrl, setBaseUrl] = useState(PROVIDER_PRESETS.deepseek.baseUrl);
  const [model, setModel] = useState(PROVIDER_PRESETS.deepseek.models[0]);
  const [temperature, setTemperature] = useState(0.3);
  const [maxTokens, setMaxTokens] = useState(1500);
  const [keyPreview, setKeyPreview] = useState("");
  const [keySet, setKeySet] = useState(false);
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError("");
    setTestResult(null);
    getLLMSettings()
      .then((s: LLMSettings) => {
        const p = (s.provider as Provider) in PROVIDER_PRESETS ? (s.provider as Provider) : "custom";
        setProvider(p);
        setBaseUrl(s.base_url);
        setModel(s.model);
        setTemperature(s.temperature);
        setMaxTokens(s.max_tokens);
        setKeyPreview(s.api_key_preview);
        setKeySet(s.api_key_set);
        setApiKey("");
      })
      .catch(() => setError("加载配置失败"))
      .finally(() => setLoading(false));
  }, [open]);

  function handleProviderChange(p: Provider) {
    setProvider(p);
    if (p !== "custom") {
      setBaseUrl(PROVIDER_PRESETS[p].baseUrl);
      const models = PROVIDER_PRESETS[p].models;
      if (!models.includes(model)) {
        setModel(models[0]);
      }
    }
    setTestResult(null);
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    setTestResult(null);
    try {
      const payload: Parameters<typeof updateLLMSettings>[0] = {
        provider,
        base_url: baseUrl,
        model,
        temperature,
        max_tokens: maxTokens,
      };
      if (apiKey.trim()) {
        payload.api_key = apiKey.trim();
      }
      const updated = await updateLLMSettings(payload);
      setKeyPreview(updated.api_key_preview);
      setKeySet(updated.api_key_set);
      setApiKey("");
      onClose();
    } catch {
      setError("保存失败，请检查输入");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testLLMConnection();
      setTestResult(result);
    } catch {
      setTestResult({ success: false, message: "请求异常，请检查后端连接" });
    } finally {
      setTesting(false);
    }
  }

  if (!open) return null;

  const presetModels = PROVIDER_PRESETS[provider].models;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal settings-modal" onClick={(e) => e.stopPropagation()}>
        <h3>模型配置</h3>

        {loading ? (
          <p className="settings-loading">加载中…</p>
        ) : (
          <>
            {/* 供应商选择 */}
            <div className="settings-field">
              <label className="settings-label">供应商</label>
              <div className="settings-provider-tabs">
                {(["deepseek", "openai", "custom"] as Provider[]).map((p) => (
                  <button
                    key={p}
                    className={`provider-tab ${provider === p ? "provider-tab-active" : ""}`}
                    onClick={() => handleProviderChange(p)}
                  >
                    {PROVIDER_PRESETS[p].label}
                  </button>
                ))}
              </div>
            </div>

            {/* API Key */}
            <div className="settings-field">
              <label className="settings-label">
                API Key
                {keySet && !apiKey && (
                  <span className="settings-key-badge">已设置 · {keyPreview}</span>
                )}
              </label>
              <div className="settings-key-row">
                <input
                  type={showKey ? "text" : "password"}
                  className="settings-input"
                  placeholder={keySet ? "输入新 Key 可替换（留空保留现有）" : "请输入 API Key"}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  autoComplete="off"
                />
                <button
                  className="settings-eye-btn"
                  onClick={() => setShowKey(!showKey)}
                  title={showKey ? "隐藏" : "显示"}
                >
                  {showKey ? "🙈" : "👁"}
                </button>
              </div>
              <p className="settings-hint">
                Key 通过系统 keychain（Windows 凭据管理器 / macOS Keychain）加密存储，不写入任何文件
              </p>
            </div>

            {/* Base URL */}
            <div className="settings-field">
              <label className="settings-label">API Base URL</label>
              <input
                type="text"
                className="settings-input"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.deepseek.com/v1"
              />
            </div>

            {/* 模型 */}
            <div className="settings-field">
              <label className="settings-label">模型</label>
              {presetModels.length > 0 ? (
                <div className="settings-model-row">
                  <select
                    className="settings-select"
                    value={presetModels.includes(model) ? model : "__custom__"}
                    onChange={(e) => {
                      if (e.target.value !== "__custom__") setModel(e.target.value);
                    }}
                  >
                    {presetModels.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                    <option value="__custom__">自定义…</option>
                  </select>
                  {!presetModels.includes(model) && (
                    <input
                      type="text"
                      className="settings-input"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      placeholder="输入模型名"
                    />
                  )}
                </div>
              ) : (
                <input
                  type="text"
                  className="settings-input"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="例：my-model-v1"
                />
              )}
            </div>

            {/* 高级参数 */}
            <div className="settings-advanced">
              <div className="settings-field settings-field-inline">
                <label className="settings-label">
                  Temperature
                  <span className="settings-value-badge">{temperature.toFixed(1)}</span>
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                  className="settings-slider"
                />
              </div>
              <div className="settings-field settings-field-inline">
                <label className="settings-label">Max Tokens</label>
                <input
                  type="number"
                  className="settings-input settings-input-sm"
                  min="100"
                  max="8000"
                  step="100"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(Number(e.target.value))}
                />
              </div>
            </div>

            {/* 测试结果 */}
            {testResult && (
              <div className={`settings-test-result ${testResult.success ? "test-ok" : "test-fail"}`}>
                {testResult.success ? "✓" : "✗"} {testResult.message}
              </div>
            )}

            {error && <p className="settings-error">{error}</p>}
          </>
        )}

        <div className="modal-actions">
          <button onClick={handleTest} disabled={testing || loading} className="settings-test-btn">
            {testing ? "测试中…" : "测试连接"}
          </button>
          <div style={{ flex: 1 }} />
          <button onClick={onClose} disabled={saving}>取消</button>
          <button className="primary" onClick={handleSave} disabled={saving || loading}>
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
