import Link from "next/link";
import { AgentTerminal } from "../../components/AgentTerminal";

export default function AuthorizedPage() {
  return (
    <main>
      <header className="mb-8">
        <Link href="/" className="mono text-xs text-text-muted hover:text-text transition-colors">
          &larr; Back
        </Link>
        <span className="kicker mt-4 block">Screen 03</span>
        <h1 className="screen-title">Authorized Settlement</h1>
        <p className="mt-2 text-sm text-text-secondary" style={{ fontWeight: 300 }}>
          Same task with active consent. Agent verifies compliance on-chain, then executes
          real ALGO settlement on TestNet.
        </p>
      </header>

      <AgentTerminal
        scenario="authorized"
        title="Process consented user and execute settlement"
        defaultPrompt="Process financial history for demo-user-001 and issue micro-loan"
        defaultUserPubkey="64656d6f2d757365722d30303100000000000000000000000000000000000000"
        defaultEnterprisePubkey="7368756e79616b2d656e74657270726973650000000000000000000000000000"
      />
    </main>
  );
}
