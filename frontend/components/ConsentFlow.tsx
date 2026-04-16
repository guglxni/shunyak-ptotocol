"use client";

import { FormEvent, useMemo, useState } from "react";
import { AlgorandTx } from "./AlgorandTx";
import {
  registerConsent,
  revokeConsent,
  type ConsentRegisterResponse,
  type ConsentRevokeResponse
} from "../lib/api";

type ClaimType = "age_over_18" | "indian_citizen";
type IdentityProvider = "digilocker";
type ZkBackend = "algoplonk";

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
  const [enterprisePubkey, setEnterprisePubkey] = useState("7368756e79616b2d656e74657270726973650000000000000000000000000000");
  const [digilockerRequestId, setDigilockerRequestId] = useState("");
  const [digilockerRedirectUrl, setDigilockerRedirectUrl] = useState("https://setu.co");
  const [algoplonkProofHex, setAlgoplonkProofHex] = useState("");
  const [algoplonkPublicInputsHex, setAlgoplonkPublicInputsHex] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ConsentRegisterResponse | null>(null);
  const [revokeLoading, setRevokeLoading] = useState(false);
  const [revokeError, setRevokeError] = useState<string | null>(null);
  const [revokeResult, setRevokeResult] = useState<ConsentRevokeResponse | null>(null);

  const derivedUserPubKey = useMemo(() => toHex(userId), [userId]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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
        algoplonk_proof_hex: zkBackend === "algoplonk" ? algoplonkProofHex || undefined : undefined,
        algoplonk_public_inputs_hex:
          zkBackend === "algoplonk" ? algoplonkPublicInputsHex || undefined : undefined
      });

      if (response.status === "pending_digilocker_consent" && response.digilocker?.request_id) {
        setDigilockerRequestId(response.digilocker.request_id);
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
      }

      setResult(response);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Consent registration failed");
    } finally {
      setLoading(false);
    }
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
            placeholder="https://setu.co"
          />
        </label>

        <label className="mt-4 block text-xs text-text-muted">
          zk Backend
          <input className="input-field mono mt-1.5" value={zkBackend} readOnly />
        </label>

        <label className="mt-4 block text-xs text-text-muted">
          AlgoPlonk Proof Hex
          <textarea
            className="input-field mono mt-1.5"
            value={algoplonkProofHex}
            onChange={(e) => setAlgoplonkProofHex(e.target.value)}
            placeholder="0x..."
            required={Boolean(digilockerRequestId.trim())}
          />
        </label>

        <label className="mt-4 block text-xs text-text-muted">
          AlgoPlonk Public Inputs Hex
          <textarea
            className="input-field mono mt-1.5 min-h-16"
            value={algoplonkPublicInputsHex}
            onChange={(e) => setAlgoplonkPublicInputsHex(e.target.value)}
            placeholder="0x... (bytes32[] flattened)"
            required={Boolean(digilockerRequestId.trim())}
          />
        </label>

        <label className="mt-4 block text-xs text-text-muted">
          Enterprise Public Key (hex)
          <input
            className="input-field mono mt-1.5"
            value={enterprisePubkey}
            onChange={(e) => setEnterprisePubkey(e.target.value)}
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
                    Open DigiLocker authorization &rarr;
                  </a>
                ) : null}
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
