"use client";

import { useEffect, useState } from "react";
import { fetchAlgorandShowcase, type AlgorandShowcaseResponse } from "../lib/api";

export function AlgorandShowcase() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AlgorandShowcaseResponse | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchAlgorandShowcase();
      setData(payload);
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
      <div className="panel p-6">
        <p className="kicker">Algorand SDK Snapshot</p>
        {loading ? <p className="mt-3 text-fog">Loading network snapshot...</p> : null}
        {error ? <p className="mt-3 text-red-300">{error}</p> : null}

        {data ? (
          <pre className="mono mt-3 max-h-80 overflow-auto rounded-xl bg-black/30 p-3 text-xs text-fog">
            {JSON.stringify(data.sdk_snapshot, null, 2)}
          </pre>
        ) : null}

        <button
          className="mt-4 rounded-xl border border-ocean/40 bg-ocean/10 px-4 py-2 text-sm text-ocean"
          onClick={() => void load()}
          type="button"
        >
          Refresh Snapshot
        </button>
      </div>

      <div className="space-y-4">
        <div className="panel p-6">
          <p className="kicker">AlgoKit Availability</p>
          <p className="mono mt-3 text-sm text-paper">
            CLI: {data?.algokit.cli_available ? "available" : "not available"}
          </p>
          <p className="mono mt-1 text-xs text-fog">{data?.algokit.cli_version ?? "-"}</p>

          <p className="mono mt-3 text-sm text-paper">
            algokit-utils: {data?.algokit.utils_available ? "installed" : "not installed"}
          </p>
          <p className="mono mt-1 text-xs text-fog">{data?.algokit.utils_version ?? "-"}</p>
        </div>

        <div className="panel p-6">
          <p className="kicker">Signer Account</p>
          <p className="mono mt-3 break-all text-xs text-fog">
            address: {data?.sender_account.address ?? "not configured"}
          </p>
          <p className="mono mt-2 text-xs text-fog">
            balance (microALGO): {data?.sender_account.balance_microalgo ?? "-"}
          </p>
          <p className="mono mt-2 text-xs text-fog">
            warning threshold (microALGO): {data?.sender_account.warning_threshold_microalgo ?? "-"}
          </p>

          {data?.sender_account.low_balance_warning ? (
            <div className="mt-3 rounded-xl border border-amber-300/40 bg-amber-300/10 p-3">
              <p className="mono text-xs text-amber-200">
                {data.sender_account.warning_message ??
                  "Signer balance is low. Re-fund TestNet wallet to avoid failed settlements."}
              </p>
            </div>
          ) : null}

          <p className="mt-3 text-xs text-fog">
            Configure SHUNYAK_AGENT_MNEMONIC and fund it on TestNet for full on-chain consent +
            settlement flows.
          </p>
        </div>

        <div className="panel p-6">
          <p className="kicker">Engine Configuration</p>
          <p className="mono mt-3 text-xs text-fog">
            consent source: {data?.consent_engine?.source_mode ?? "unknown"}
          </p>
          <p className="mono mt-2 text-xs text-fog">
            consent app id: {data?.consent_engine?.app_id ?? "not configured"}
          </p>
          <p className="mono mt-2 text-xs text-fog">
            settlement mode: {data?.settlement_engine?.asset_mode ?? "unknown"}
          </p>
          <p className="mono mt-2 text-xs text-fog">
            settlement asset id: {data?.settlement_engine?.asset_id ?? "not configured"}
          </p>
          <p className="mono mt-2 text-xs text-fog">
            identity provider: {data?.identity_engine?.provider ?? "unknown"}
          </p>
          <p className="mono mt-2 text-xs text-fog">
            digilocker configured: {data?.identity_engine?.digilocker_configured ? "yes" : "no"}
          </p>
          <p className="mono mt-2 text-xs text-fog">zk backend: {data?.zk_engine?.backend ?? "unknown"}</p>
          <p className="mono mt-2 text-xs text-fog">
            zk verify app id: {data?.zk_engine?.verify_app_id ?? "not configured"}
          </p>
          <p className="mono mt-2 text-xs text-fog">
            zk onchain required: {data?.zk_engine?.onchain_required ? "true" : "false"}
          </p>
        </div>
      </div>
    </section>
  );
}
