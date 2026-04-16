"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { AlgorandTx } from "./AlgorandTx";
import { AuditViewer } from "./AuditViewer";
import {
  executeAgent,
  openAgentEventStream,
  type AgentEvent,
  type AgentExecutePayload,
  type AgentExecuteResponse
} from "../lib/api";

type AgentTerminalProps = {
  title: string;
  defaultPrompt: string;
  defaultUserPubkey: string;
  defaultEnterprisePubkey: string;
};

function eventColor(kind: AgentEvent["kind"]): string {
  if (kind === "success") {
    return "text-moss";
  }
  if (kind === "error") {
    return "text-red-300";
  }
  return "text-fog";
}

export function AgentTerminal({
  title,
  defaultPrompt,
  defaultUserPubkey,
  defaultEnterprisePubkey
}: AgentTerminalProps) {
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [userPubkey, setUserPubkey] = useState(defaultUserPubkey);
  const [enterprisePubkey, setEnterprisePubkey] = useState(defaultEnterprisePubkey);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AgentExecuteResponse | null>(null);
  const [consentToken, setConsentToken] = useState<string>("");
  const [operatorToken, setOperatorToken] = useState<string>("");
  const [streamEvents, setStreamEvents] = useState<AgentEvent[]>([]);

  const defaultEvents = useMemo(
    () => [
      { phase: "startup", message: "Dolios runtime initialized", kind: "info" as const },
      { phase: "compliance", message: "Waiting for execution", kind: "info" as const }
    ],
    []
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const storageKey = `shunyak:consent:${userPubkey}:${enterprisePubkey}`;
    const token = window.localStorage.getItem(storageKey) ?? "";
    setConsentToken(token);

    const operator = window.localStorage.getItem("shunyak:operator-token") ?? "";
    setOperatorToken(operator);
  }, [enterprisePubkey, userPubkey]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setStreamEvents([]);

    const payload: AgentExecutePayload = {
      prompt,
      user_pubkey: userPubkey,
      enterprise_pubkey: enterprisePubkey,
      amount_microalgo: 1_000_000,
      consent_token: consentToken || undefined,
      operator_token: operatorToken || undefined
    };

    if (typeof window !== "undefined") {
      const storageKey = `shunyak:consent:${userPubkey}:${enterprisePubkey}`;
      if (consentToken) {
        window.localStorage.setItem(storageKey, consentToken);
      } else {
        window.localStorage.removeItem(storageKey);
      }

      if (operatorToken) {
        window.localStorage.setItem("shunyak:operator-token", operatorToken);
      } else {
        window.localStorage.removeItem("shunyak:operator-token");
      }
    }

    try {
      if (typeof window !== "undefined" && "EventSource" in window) {
        const streamedResponse = await new Promise<AgentExecuteResponse>((resolve, reject) => {
          let completed = false;

          let source: EventSource | null = null;
          const closeSource = () => {
            if (source) {
              source.close();
              source = null;
            }
          };

          openAgentEventStream(
            payload,
            (envelope) => {
              if (completed) {
                return;
              }

              if (envelope.type === "event") {
                setStreamEvents((previous) => [...previous, envelope.event]);
                return;
              }

              if (envelope.type === "final") {
                completed = true;
                closeSource();
                resolve(envelope.result);
                return;
              }

              if (envelope.type === "error") {
                completed = true;
                closeSource();
                reject(new Error(envelope.error || "SSE stream error"));
              }
            },
            () => {
              if (!completed) {
                completed = true;
                closeSource();
                reject(new Error("SSE stream disconnected"));
              }
            }
          )
            .then((createdSource) => {
              source = createdSource;
            })
            .catch((streamError) => {
              if (!completed) {
                completed = true;
                reject(streamError);
              }
            });
        });

        setResult(streamedResponse);
      } else {
        const response = await executeAgent(payload);
        setResult(response);
      }
    } catch (submitError) {
      try {
        const fallbackResponse = await executeAgent(payload);
        setResult(fallbackResponse);
      } catch (fallbackError) {
        const message = fallbackError instanceof Error ? fallbackError.message : "Agent execution failed";
        const streamMessage = submitError instanceof Error ? submitError.message : "stream failure";
        setError(`${message} (stream fallback: ${streamMessage})`);
      }
    } finally {
      setLoading(false);
    }
  }

  const events = result?.events ?? (streamEvents.length > 0 ? streamEvents : defaultEvents);

  return (
    <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
      <form className="panel p-6" onSubmit={onSubmit}>
        <p className="kicker">Agent Execution</p>
        <h2 className="mt-2 text-2xl font-semibold">{title}</h2>

        <label className="mt-5 block text-sm text-fog">
          Prompt
          <textarea
            className="mt-1 min-h-24 w-full rounded-xl border border-white/20 bg-black/25 p-3 text-paper outline-none ring-ocean/40 focus:ring"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            required
          />
        </label>

        <label className="mt-4 block text-sm text-fog">
          User Public Key (hex)
          <input
            className="mono mt-1 w-full rounded-xl border border-white/20 bg-black/25 p-3 text-paper outline-none ring-ocean/40 focus:ring"
            value={userPubkey}
            onChange={(e) => setUserPubkey(e.target.value)}
            required
          />
        </label>

        <label className="mt-4 block text-sm text-fog">
          Enterprise Public Key (hex)
          <input
            className="mono mt-1 w-full rounded-xl border border-white/20 bg-black/25 p-3 text-paper outline-none ring-ocean/40 focus:ring"
            value={enterprisePubkey}
            onChange={(e) => setEnterprisePubkey(e.target.value)}
            required
          />
        </label>

        <label className="mt-4 block text-sm text-fog">
          Operator Token
          <input
            className="mono mt-1 w-full rounded-xl border border-white/20 bg-black/25 p-3 text-paper outline-none ring-ocean/40 focus:ring"
            value={operatorToken}
            onChange={(e) => setOperatorToken(e.target.value)}
            placeholder="required in hardened/deployed mode"
          />
        </label>

        <label className="mt-4 block text-sm text-fog">
          Consent Token (optional override)
          <textarea
            className="mono mt-1 min-h-20 w-full rounded-xl border border-white/20 bg-black/25 p-3 text-paper outline-none ring-ocean/40 focus:ring"
            value={consentToken}
            onChange={(e) => setConsentToken(e.target.value)}
            placeholder="paste a valid consent token to force authorized path"
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          className="mt-6 inline-flex items-center rounded-xl border border-ocean/40 bg-ocean/10 px-5 py-3 font-medium text-ocean disabled:opacity-50"
        >
          {loading ? "Executing..." : "Execute Agent"}
        </button>

        <p className="mono mt-3 text-xs text-fog">
          consent token: {consentToken ? "present" : "missing"}
        </p>
        <p className="mono mt-1 text-xs text-fog">
          operator token: {operatorToken ? "present" : "missing"}
        </p>

        {result ? (
          <p className="mt-4 text-sm text-paper">
            Outcome: <span className="mono text-ember">{result.outcome_message}</span>
          </p>
        ) : null}

        {error ? <p className="mt-4 text-sm text-red-300">{error}</p> : null}
      </form>

      <div className="space-y-4">
        <div className="panel p-6">
          <p className="kicker">Live Agent Output</p>
          <ul className="mono mt-3 space-y-2 text-sm">
            {events.map((eventItem, index) => (
              <li key={`${eventItem.phase}-${index}`} className={eventColor(eventItem.kind)}>
                [{eventItem.phase}] {eventItem.message}
              </li>
            ))}
          </ul>
        </div>

        {result?.settlement ? (
          <div className="space-y-3">
            <AlgorandTx
              txid={result.settlement.txid}
              explorerUrl={result.settlement.explorer_url}
              confirmedRound={result.settlement.confirmed_round}
            />
            <div className="panel p-4">
              <p className="kicker">Settlement Details</p>
              <p className="mono mt-2 text-xs text-fog">mode: {result.settlement.mode ?? "unknown"}</p>
              <p className="mono mt-2 break-all text-xs text-fog">
                receiver: {result.settlement.receiver ?? "not provided"}
              </p>
              {typeof result.settlement.asset_id === "number" ? (
                <p className="mono mt-2 text-xs text-fog">asset_id: {result.settlement.asset_id}</p>
              ) : null}
              {result.settlement.fallback_reason ? (
                <p className="mono mt-2 text-xs text-amber-200">
                  fallback_reason: {result.settlement.fallback_reason}
                </p>
              ) : null}
            </div>
          </div>
        ) : null}

        <AuditViewer items={result?.audit_entries ?? []} />
      </div>
    </div>
  );
}
