"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { AlgorandTx } from "./AlgorandTx";
import {
  fetchDemoContext,
  registerConsent,
  revokeConsent,
  type ConsentRegisterResponse,
  type ConsentRevokeResponse
} from "../lib/api";

type ClaimType = "age_over_18" | "indian_citizen";
type IdentityProvider = "digilocker";
type ZkBackend = "algoplonk";

type PendingDigiLockerState = {
  user_id?: string;
  claim_type?: ClaimType;
  enterprise_pubkey?: string;
  digilocker_request_id?: string;
  digilocker_redirect_url?: string;
};

const PENDING_DIGILOCKER_STORAGE_KEY = "shunyak:digilocker-pending";
const DEFAULT_DIGILOCKER_REDIRECT_URL = "https://shunyak-protocol.vercel.app/consent";
const DEFAULT_ENTERPRISE_PUBKEY = "7368756e79616b2d656e74657270726973650000000000000000000000000000";

function toHex(input: string): string {
  const bytes = new TextEncoder().encode(input);
  return Array.from(bytes)
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 64)
    .padEnd(64, "0");
}

export function ConsentFlow() {
  const [userId, setUserId] = useState("demo-user-001");
  const [claimType, setClaimType] = useState<ClaimType>("age_over_18");
  const [identityProvider] = useState<IdentityProvider>("digilocker");
  const [zkBackend] = useState<ZkBackend>("algoplonk");
  const [enterprisePubkey, setEnterprisePubkey] = useState(DEFAULT_ENTERPRISE_PUBKEY);
  const [digilockerRequestId, setDigilockerRequestId] = useState("");
  const [digilockerRedirectUrl, setDigilockerRedirectUrl] = useState(DEFAULT_DIGILOCKER_REDIRECT_URL);
  const [algoplonkProofHex, setAlgoplonkProofHex] = useState("");
  const [algoplonkPublicInputsHex, setAlgoplonkPublicInputsHex] = useState("");
  const [showAdvancedInputs, setShowAdvancedInputs] = useState(false);
  const [contextLoading, setContextLoading] = useState(true);
  const [contextError, setContextError] = useState<string | null>(null);
  const [contextWarnings, setContextWarnings] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ConsentRegisterResponse | null>(null);
  const [revokeLoading, setRevokeLoading] = useState(false);
  const [revokeError, setRevokeError] = useState<string | null>(null);
  const [revokeResult, setRevokeResult] = useState<ConsentRevokeResponse | null>(null);

  const derivedUserPubKey = useMemo(() => toHex(userId), [userId]);

  useEffect(() => {
    let active = true;
    setContextLoading(true);
    setContextError(null);

    fetchDemoContext()
      .then((context) => {
        if (!active) return;
        setUserId(context.consent.user_id || "demo-user-001");
        setClaimType(context.consent.claim_type || "age_over_18");
        setEnterprisePubkey(context.consent.enterprise_pubkey || DEFAULT_ENTERPRISE_PUBKEY);
        setDigilockerRedirectUrl(
          context.consent.digilocker_redirect_url || DEFAULT_DIGILOCKER_REDIRECT_URL
        );
        setContextWarnings(context.token_warnings ?? []);

        if (typeof window !== "undefined") {
          const pendingRaw = window.localStorage.getItem(PENDING_DIGILOCKER_STORAGE_KEY);
          if (pendingRaw) {
            try {
              const pending = JSON.parse(pendingRaw) as PendingDigiLockerState;
              if (pending.user_id) {
                setUserId(pending.user_id);
              }
              if (pending.claim_type) {
                setClaimType(pending.claim_type);
              }
              if (pending.enterprise_pubkey) {
                setEnterprisePubkey(pending.enterprise_pubkey);
              }
              if (pending.digilocker_request_id) {
                setDigilockerRequestId(pending.digilocker_request_id);
              }
              if (pending.digilocker_redirect_url) {
                setDigilockerRedirectUrl(pending.digilocker_redirect_url);
              }
            } catch {
              window.localStorage.removeItem(PENDING_DIGILOCKER_STORAGE_KEY);
            }
          }
        }
      })
      .catch((loadError) => {
        if (!active) return;
        setContextError(loadError instanceof Error ? loadError.message : "Failed to load demo defaults");
      })
      .finally(() => {
        if (active) {
          setContextLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  async function submitConsentRegistration() {
    setLoading(true);
    setError(null);
    setResult(null);
    setRevokeError(null);
    setRevokeResult(null);

    try {
      const response = await registerConsent({
        user_id: userId,
        claim_type: claimType,
        enterprise_pubkey: enterprisePubkey,
        expiry_days: 30,
        identity_provider: identityProvider,
        digilocker_request_id: digilockerRequestId || undefined,
        digilocker_redirect_url: digilockerRedirectUrl || undefined,
        zk_backend: zkBackend,
        algoplonk_proof_hex:
          zkBackend === "algoplonk" ? algoplonkProofHex.trim() || undefined : undefined,
        algoplonk_public_inputs_hex:
          zkBackend === "algoplonk" ? algoplonkPublicInputsHex.trim() || undefined : undefined
      });

      if (response.status === "pending_digilocker_consent" && response.digilocker?.request_id) {
        setDigilockerRequestId(response.digilocker.request_id);

        if (typeof window !== "undefined") {
          window.localStorage.setItem(
            PENDING_DIGILOCKER_STORAGE_KEY,
            JSON.stringify({
              user_id: userId,
              claim_type: claimType,
              enterprise_pubkey: enterprisePubkey,
              digilocker_request_id: response.digilocker.request_id,
              digilocker_redirect_url: digilockerRedirectUrl
            } satisfies PendingDigiLockerState)
          );
        }

        const authUrl = response.digilocker?.auth_url;
        if (typeof window !== "undefined" && authUrl) {
          window.setTimeout(() => {
            window.location.assign(authUrl);
          }, 250);
        }
      }

      if (
        typeof window !== "undefined" &&
        response.status === "consent_registered" &&
        response.user_pubkey &&
        response.enterprise_pubkey &&
        response.consent_token
      ) {
        const storageKey = `shunyak:consent:${response.user_pubkey}:${response.enterprise_pubkey}`;
        window.localStorage.setItem(storageKey, response.consent_token);
        window.localStorage.setItem(
          "shunyak:last-consent-profile",
          JSON.stringify({
            user_id: userId,
            user_pubkey: response.user_pubkey,
            enterprise_pubkey: response.enterprise_pubkey,
            consent_token: response.consent_token,
            updated_at: Date.now()
          })
        );
        window.localStorage.removeItem(PENDING_DIGILOCKER_STORAGE_KEY);
      }

      setResult(response);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Consent registration failed");
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitConsentRegistration();
  }

  async function onRevokeConsent() {
    if (!result?.user_pubkey || !result?.enterprise_pubkey) {
      return;
    }

    setRevokeLoading(true);
    setRevokeError(null);
    setRevokeResult(null);

    try {
      const response = await revokeConsent({
        user_pubkey: result.user_pubkey,
        enterprise_pubkey: result.enterprise_pubkey
      });

      if (typeof window !== "undefined") {
        const storageKey = `shunyak:consent:${result.user_pubkey}:${result.enterprise_pubkey}`;
        window.localStorage.removeItem(storageKey);

        const lastProfileRaw = window.localStorage.getItem("shunyak:last-consent-profile");
        if (lastProfileRaw) {
          try {
            const parsed = JSON.parse(lastProfileRaw) as {
              user_pubkey?: string;
              enterprise_pubkey?: string;
            };
            if (
              parsed.user_pubkey === result.user_pubkey &&
              parsed.enterprise_pubkey === result.enterprise_pubkey
            ) {
              window.localStorage.removeItem("shunyak:last-consent-profile");
            }
          } catch {
            window.localStorage.removeItem("shunyak:last-consent-profile");
          }
        }
      }

      setRevokeResult(response);
    } catch (submitError) {
      setRevokeError(submitError instanceof Error ? submitError.message : "Consent revoke failed");
    } finally {
      setRevokeLoading(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
      <form className="card p-6" onSubmit={onSubmit}>
        <p className="kicker">Consent Registration</p>
        <h2 className="mt-2 text-xl font-semibold">Generate proof and commit consent state</h2>

        {contextLoading ? (
          <p className="mt-4 text-xs text-text-muted">Loading backend demo defaults...</p>
        ) : null}
        {contextError ? <p className="mt-4 text-sm text-warning">{contextError}</p> : null}
        {contextWarnings.length > 0 ? (
          <div className="mt-4 rounded-lg border border-warning/30 bg-warning/5 p-3">
            <p className="text-xs text-warning">
              Some backend-generated tokens are unavailable. Demo flow may require runtime secret setup.
            </p>
          </div>
        ) : null}

        <label className="mt-5 block text-xs text-text-muted">
          User ID
          <input
            className="input-field mt-1.5"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            required
          />
        </label>

        <label className="mt-4 block text-xs text-text-muted">
          Claim Type
          <select
            className="input-field mt-1.5"
            value={claimType}
            onChange={(e) => setClaimType(e.target.value as ClaimType)}
          >
            <option value="age_over_18">age_over_18</option>
            <option value="indian_citizen">indian_citizen</option>
          </select>
        </label>

        <label className="mt-4 block text-xs text-text-muted">
          Identity Provider
          <input className="input-field mono mt-1.5" value={identityProvider} readOnly />
        </label>

        <label className="mt-4 block text-xs text-text-muted">
          DigiLocker Request ID
          <input
            className="input-field mono mt-1.5"
            value={digilockerRequestId}
            onChange={(e) => setDigilockerRequestId(e.target.value)}
            placeholder="dg-req-..."
          />
        </label>

        <label className="mt-4 block text-xs text-text-muted">
          DigiLocker Redirect URL
          <input
            className="input-field mt-1.5"
            value={digilockerRedirectUrl}
            onChange={(e) => setDigilockerRedirectUrl(e.target.value)}
            placeholder={DEFAULT_DIGILOCKER_REDIRECT_URL}
          />
        </label>

        <label className="mt-4 block text-xs text-text-muted">
          zk Backend
          <input className="input-field mono mt-1.5" value={zkBackend} readOnly />
        </label>

        <div className="mt-4 rounded-lg border border-border-subtle bg-bg p-3">
          <p className="text-xs text-text-muted">
            AlgoPlonk proof/public inputs are generated by backend for demo flows.
          </p>
          <button
            type="button"
            className="mono mt-2 text-xs text-text-secondary underline underline-offset-2"
            onClick={() => setShowAdvancedInputs((previous) => !previous)}
          >
            {showAdvancedInputs ? "Hide advanced override" : "Show advanced override"}
          </button>
        </div>

        {showAdvancedInputs ? (
          <>
            <label className="mt-4 block text-xs text-text-muted">
              AlgoPlonk Proof Hex (optional override)
              <textarea
                className="input-field mono mt-1.5"
                value={algoplonkProofHex}
                onChange={(e) => setAlgoplonkProofHex(e.target.value)}
                placeholder="0x..."
              />
            </label>

            <label className="mt-4 block text-xs text-text-muted">
              AlgoPlonk Public Inputs Hex (optional override)
              <textarea
                className="input-field mono mt-1.5 min-h-16"
                value={algoplonkPublicInputsHex}
                onChange={(e) => setAlgoplonkPublicInputsHex(e.target.value)}
                placeholder="0x... (bytes32[] flattened)"
              />
            </label>
          </>
        ) : null}

        <label className="mt-4 block text-xs text-text-muted">
          Enterprise Public Key (hex)
          <input
            className="input-field mono mt-1.5"
            value={enterprisePubkey}
            readOnly
            minLength={64}
            maxLength={64}
            required
          />
        </label>

        <div className="mt-5 rounded-lg border border-border-subtle bg-bg p-3">
          <p className="text-xs text-text-muted">Derived User Public Key</p>
          <p className="mono mt-1 break-all text-xs text-text-secondary">{derivedUserPubKey}</p>
        </div>

        <button type="submit" disabled={loading} className="btn-primary mt-6">
          {loading ? "Registering..." : "Register Consent"}
        </button>

        {error ? <p className="mt-4 text-sm text-error">{error}</p> : null}
      </form>

      <div className="space-y-4">
        <div className="card p-5">
          <p className="kicker">Pipeline</p>
          <ul className="mono mt-3 space-y-1.5 text-xs text-text-secondary">
            {(result?.steps ?? [
              "Awaiting submission",
              "identity provider attestation",
              "claim hash derivation",
              "proof generation",
              "Algorand testnet transaction"
            ]).map((step) => (
              <li key={step} className="flex items-start gap-2">
                <span className="text-text-muted">&bull;</span>
                {step}
              </li>
            ))}
          </ul>
        </div>

        {result ? (
          <div className="space-y-3">
            {result.txid && result.explorer_url ? (
              <AlgorandTx txid={result.txid} explorerUrl={result.explorer_url} />
            ) : null}

            {result.status === "pending_digilocker_consent" ? (
              <div className="card p-4">
                <p className="kicker">DigiLocker Pending</p>
                <p className="mono mt-2 text-xs text-text-secondary">
                  request_id: {result.digilocker?.request_id ?? "not available"}
                </p>
                <p className="mono mt-1 text-xs text-text-muted">
                  status: {result.digilocker?.status ?? "PENDING"}
                </p>
                {result.digilocker?.auth_url ? (
                  <a
                    href={result.digilocker.auth_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mono mt-3 inline-block text-xs text-text-secondary underline underline-offset-2"
                  >
                    Redirecting to DigiLocker login... open manually &rarr;
                  </a>
                ) : null}
                <button
                  type="button"
                  className="btn-secondary mt-3"
                  onClick={() => void submitConsentRegistration()}
                  disabled={loading}
                >
                  {loading ? "Checking..." : "I completed DigiLocker - Continue"}
                </button>
              </div>
            ) : null}

            <div className="card p-4">
              <p className="kicker">Execution Mode</p>
              <div className="mono mt-2 space-y-1 text-xs text-text-secondary">
                <p>status: {result.status ?? "unknown"}</p>
                <p>identity_provider: {result.identity_provider ?? "unknown"}</p>
                <p>zk_backend: {result.zk_backend ?? "unknown"}</p>
                <p>zk_verification_mode: {result.zk_verification_mode ?? "unknown"}</p>
                <p>tx_mode: {result.tx_mode ?? "unknown"}</p>
                <p>consent_source: {result.consent_source ?? "unknown"}</p>
                {result.digilocker?.scope?.length ? (
                  <p className="break-all">digilocker_scope: {result.digilocker.scope.join(",")}</p>
                ) : null}
                {result.digilocker?.aadhaar_masked_number ? (
                  <p>aadhaar_masked: {result.digilocker.aadhaar_masked_number}</p>
                ) : null}
                {result.aadhaar?.trace_id ? (
                  <p className="break-all">aadhaar_trace_id: {result.aadhaar.trace_id}</p>
                ) : null}
                {typeof result.algoplonk?.proof_chunk_count === "number" ? (
                  <p>algoplonk_chunks: {result.algoplonk.proof_chunk_count}</p>
                ) : null}
                {result.algoplonk?.onchain_error ? (
                  <p className="text-warning">algoplonk_onchain_error: {result.algoplonk.onchain_error}</p>
                ) : null}
                {result.fallback_reason ? (
                  <p className="text-warning">fallback_reason: {result.fallback_reason}</p>
                ) : null}
              </div>
            </div>

            {result.status === "consent_registered" && result.user_pubkey && result.enterprise_pubkey ? (
              <div className="card p-4">
                <p className="kicker">Revocation</p>
                <p className="mt-2 text-xs text-text-muted">
                  Revoke consent to demonstrate full lifecycle on-chain.
                </p>
                <button
                  type="button"
                  disabled={revokeLoading}
                  onClick={onRevokeConsent}
                  className="btn-danger mt-3"
                >
                  {revokeLoading ? "Revoking..." : "Revoke Consent"}
                </button>
                {revokeResult?.txid ? (
                  <p className="mono mt-3 break-all text-xs text-text-secondary">
                    revoke_txid: {revokeResult.txid}
                  </p>
                ) : null}
                {revokeResult?.box_status ? (
                  <p className="mono mt-1 text-xs text-text-muted">box_status: {revokeResult.box_status}</p>
                ) : null}
                {revokeError ? <p className="mt-3 text-sm text-error">{revokeError}</p> : null}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="card p-4">
            <p className="kicker">Awaiting Transaction</p>
            <p className="mt-2 text-xs text-text-muted">Submit a consent registration to generate output.</p>
          </div>
        )}
      </div>
    </div>
  );
}
