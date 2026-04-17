"use client";

import { useEffect, useState } from "react";
import {
  fetchAlgorandShowcase,
  fetchDemoContext,
  type AlgorandShowcaseResponse,
  type DemoContextResponse
} from "../lib/api";
import { liteLLMConfigSummary, loadLiteLLMConfigFromStorage } from "../lib/llm";

export function AlgorandShowcase() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AlgorandShowcaseResponse | null>(null);
  const [demoContext, setDemoContext] = useState<DemoContextResponse | null>(null);
  const [llmRouteSummary, setLlmRouteSummary] = useState("disabled");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const runtimeLLMConfig =
        typeof window !== "undefined" ? loadLiteLLMConfigFromStorage() : undefined;
      const [showcasePayload, contextPayload] = await Promise.all([
        fetchAlgorandShowcase(runtimeLLMConfig),
        fetchDemoContext()
      ]);
      setData(showcasePayload);
      setDemoContext(contextPayload);
      if (runtimeLLMConfig) {
        setLlmRouteSummary(liteLLMConfigSummary(runtimeLLMConfig));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch showcase data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <section className="grid gap-4 lg:grid-cols-2">
      <div className="card p-6">
        <p className="kicker">Algorand SDK Snapshot</p>
        {loading ? <p className="mt-3 text-sm text-text-muted">Loading network snapshot...</p> : null}
        {error ? <p className="mt-3 text-sm text-error">{error}</p> : null}

        {data ? (
          <pre className="mono mt-3 max-h-80 overflow-auto rounded-lg border border-border-subtle bg-bg p-3 text-xs text-text-secondary">
            {JSON.stringify(data.sdk_snapshot, null, 2)}
          </pre>
        ) : null}

        <button className="btn-secondary mt-4" onClick={() => void load()} type="button">
          Refresh
        </button>
      </div>

      <div className="space-y-4">
        <div className="card p-6">
          <p className="kicker">AlgoKit Runtime</p>
          <div className="mt-3 space-y-1">
            {data?.algokit.runtime ? (
              <p className="mono text-xs text-text-muted">runtime: {data.algokit.runtime}</p>
            ) : null}
            <p className="mono text-sm text-text">
              CLI: {(() => {
                if (data?.algokit.cli_status === "not_applicable") {
                  return "n/a in serverless runtime";
                }
                return data?.algokit.cli_available ? "available" : "not available";
              })()}
            </p>
            <p className="mono text-xs text-text-muted">{data?.algokit.cli_version ?? "-"}</p>
            {data?.algokit.cli_path ? (
              <p className="mono text-xs text-text-muted">path: {data.algokit.cli_path}</p>
            ) : null}
            {data?.algokit.cli_reason ? (
              <p
                className={`mono text-xs break-all ${
                  data.algokit.cli_status === "unavailable" ? "text-warning" : "text-text-muted"
                }`}
              >
                note: {data.algokit.cli_reason}
              </p>
            ) : null}
            <p className="mono mt-2 text-sm text-text">
              algokit-utils: {data?.algokit.utils_available ? "installed" : "not installed"}
            </p>
            <p className="mono text-xs text-text-muted">{data?.algokit.utils_version ?? "-"}</p>
          </div>
        </div>

        <div className="card p-6">
          <p className="kicker">Signer Account</p>
          <p className="mono mt-3 break-all text-xs text-text-secondary">
            {data?.sender_account.address ?? "not configured"}
          </p>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-text-muted">Balance</p>
              <p className="mono text-sm text-text">
                {data?.sender_account.balance_microalgo
                  ? `${(data.sender_account.balance_microalgo / 1_000_000).toFixed(4)} ALGO`
                  : "-"}
              </p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Warning Threshold</p>
              <p className="mono text-sm text-text">
                {data?.sender_account.warning_threshold_microalgo
                  ? `${(data.sender_account.warning_threshold_microalgo / 1_000_000).toFixed(4)} ALGO`
                  : "-"}
              </p>
            </div>
          </div>

          {data?.sender_account.low_balance_warning ? (
            <div className="mt-3 rounded-lg border border-warning/30 bg-warning/5 p-3">
              <p className="mono text-xs text-warning">
                {data.sender_account.warning_message ?? "Signer balance is low."}
              </p>
            </div>
          ) : null}
        </div>

        <div className="card p-6">
          <p className="kicker">Engine Configuration</p>
          <div className="mono mt-3 space-y-1.5 text-xs text-text-secondary">
            <div className="flex justify-between">
              <span className="text-text-muted">consent source</span>
              <span>{data?.consent_engine?.source_mode ?? "unknown"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">consent app id</span>
              <span>{data?.consent_engine?.app_id ?? "not configured"}</span>
            </div>
            <div className="h-px bg-border-subtle my-1" />
            <div className="flex justify-between">
              <span className="text-text-muted">settlement mode</span>
              <span>{data?.settlement_engine?.asset_mode ?? "unknown"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">identity provider</span>
              <span>{data?.identity_engine?.provider ?? "unknown"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">digilocker</span>
              <span>{data?.identity_engine?.digilocker_configured ? "configured" : "no"}</span>
            </div>
            <div className="h-px bg-border-subtle my-1" />
            <div className="flex justify-between">
              <span className="text-text-muted">zk backend</span>
              <span>{data?.zk_engine?.backend ?? "unknown"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">zk onchain required</span>
              <span>{data?.zk_engine?.onchain_required ? "true" : "false"}</span>
            </div>
            <div className="h-px bg-border-subtle my-1" />
            <div className="flex justify-between">
              <span className="text-text-muted">llm byok</span>
              <span>{data?.llm_engine?.enabled ? "enabled" : "disabled"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">llm selected route</span>
              <span className="break-all text-right">{llmRouteSummary}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">litellm sdk</span>
              <span>
                {data?.llm_engine?.litellm_installed
                  ? data?.llm_engine?.litellm_version || "installed"
                  : "not installed"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">llm provider</span>
              <span>{data?.llm_engine?.provider ?? "unknown"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">llm model</span>
              <span className="break-all text-right">{data?.llm_engine?.model ?? "unknown"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">llm api key</span>
              <span>{data?.llm_engine?.api_key_configured ? "configured" : "not set"}</span>
            </div>
            {data?.llm_engine?.error ? (
              <p className="break-all text-warning">llm_error: {data.llm_engine.error}</p>
            ) : null}
          </div>
        </div>

        <div className="card p-6">
          <p className="kicker">Demo Route Context</p>
          <div className="mono mt-3 space-y-1.5 text-xs text-text-secondary">
            <div className="flex justify-between">
              <span className="text-text-muted">operator auth required</span>
              <span>{demoContext?.requirements.operator_auth_required ? "true" : "false"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">execution token required</span>
              <span>{demoContext?.requirements.execution_token_required ? "true" : "false"}</span>
            </div>
            <div className="h-px bg-border-subtle my-1" />
            <div className="flex justify-between">
              <span className="text-text-muted">blocked route ready</span>
              <span>{demoContext?.blocked.ready ? "yes" : "no"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">authorized route ready</span>
              <span>{demoContext?.authorized.ready ? "yes" : "no"}</span>
            </div>
            {demoContext?.authorized.onchain_reason ? (
              <p className="break-all text-text-muted">authorized_reason: {demoContext.authorized.onchain_reason}</p>
            ) : null}
            {demoContext?.token_warnings?.length ? (
              <p className="break-all text-warning">token_warnings: {demoContext.token_warnings.join(" | ")}</p>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
