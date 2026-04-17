"use client";

import { FormEvent, useState } from "react";
import {
  clearLiteLLMConfigStorage,
  loadLiteLLMConfigFromStorage,
  saveLiteLLMConfigToStorage,
  type AgentLiteLLMConfig
} from "../lib/llm";

const EXAMPLE_MODELS = [
  "openai/gpt-4o-mini",
  "anthropic/claude-3-7-sonnet-latest",
  "meta-llama/llama-4-scout-17b-16e-instruct (Groq)",
  "openrouter/meta-llama/llama-3.1-70b-instruct",
  "gemini/gemini-2.5-pro",
  "ollama/llama3.2"
] as const;

export function LiteLLMConfigPanel() {
  const [config, setConfig] = useState<AgentLiteLLMConfig>(() => loadLiteLLMConfigFromStorage());
  const [status, setStatus] = useState<string>("Saved settings are used by /blocked and /authorized.");

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const saved = saveLiteLLMConfigToStorage(config);
    setConfig(saved);
    setStatus(
      saved.enabled
        ? `Saved. Active route: ${saved.provider}/${saved.model}`
        : "Saved. LiteLLM BYOK is currently disabled."
    );
  }

  function onReset() {
    clearLiteLLMConfigStorage();
    const loaded = loadLiteLLMConfigFromStorage();
    setConfig(loaded);
    setStatus("Reset to defaults. BYOK is disabled.");
  }

  return (
    <section className="card mt-8 p-6">
      <p className="kicker">Agent LLM Setup (LiteLLM / BYOK)</p>
      <h2 className="mt-2 text-xl font-semibold">Configure model/provider for Dolios execution routes</h2>
      <p className="mt-2 text-sm text-text-secondary" style={{ fontWeight: 300 }}>
        This saves in your browser and is attached to every agent execution request from blocked and authorized paths.
      </p>
      <p className="mono mt-2 text-xs text-text-muted">
        BYOK mode uses your configured model + api_base + api_key via LiteLLM at runtime.
      </p>

      <form className="mt-5 space-y-4" onSubmit={onSubmit}>
        <label className="flex items-center gap-2 text-xs text-text-muted">
          <input
            type="checkbox"
            checked={config.enabled}
            onChange={(event) => setConfig((prev) => ({ ...prev, enabled: event.target.checked }))}
          />
          Enable LiteLLM BYOK routing
        </label>

        <label className="block text-xs text-text-muted">
          Provider (free-form)
          <input
            className="input-field mono mt-1.5"
            value={config.provider}
            onChange={(event) => setConfig((prev) => ({ ...prev, provider: event.target.value }))}
            placeholder="openai | anthropic | openrouter | ollama | custom"
          />
        </label>

        <label className="block text-xs text-text-muted">
          Model (LiteLLM format)
          <input
            className="input-field mono mt-1.5"
            value={config.model}
            onChange={(event) => setConfig((prev) => ({ ...prev, model: event.target.value }))}
            placeholder="provider/model-name (or model-name for Groq)"
            required
          />
        </label>
        <p className="mono -mt-2 text-xs text-text-muted">
          For Groq use provider=groq and model without prefix (example: meta-llama/llama-4-scout-17b-16e-instruct).
        </p>

        <label className="block text-xs text-text-muted">
          API Key
          <input
            type="password"
            className="input-field mono mt-1.5"
            value={config.api_key}
            onChange={(event) => setConfig((prev) => ({ ...prev, api_key: event.target.value }))}
            placeholder="optional for local or keyless providers"
          />
        </label>

        <label className="block text-xs text-text-muted">
          API Base URL (optional)
          <input
            className="input-field mono mt-1.5"
            value={config.api_base}
            onChange={(event) => setConfig((prev) => ({ ...prev, api_base: event.target.value }))}
            placeholder="https://api.openai.com/v1"
          />
        </label>

        <label className="block text-xs text-text-muted">
          API Version (optional)
          <input
            className="input-field mono mt-1.5"
            value={config.api_version}
            onChange={(event) => setConfig((prev) => ({ ...prev, api_version: event.target.value }))}
            placeholder="2024-10-21"
          />
        </label>

        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" type="submit">
            Save LLM Settings
          </button>
          <button className="btn-secondary" type="button" onClick={onReset}>
            Reset
          </button>
        </div>
      </form>

      <p className="mono mt-4 text-xs text-text-muted">{status}</p>
      <p className="mono mt-3 text-xs text-text-muted">
        Example model strings: {EXAMPLE_MODELS.join(" | ")}
      </p>
    </section>
  );
}
