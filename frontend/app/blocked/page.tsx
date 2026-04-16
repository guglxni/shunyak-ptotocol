import Link from "next/link";
import { AgentTerminal } from "../../components/AgentTerminal";

export default function BlockedPage() {
  return (
    <main>
      <header className="mb-8">
        <Link href="/" className="mono text-xs text-text-muted hover:text-text transition-colors">
          &larr; Back
        </Link>
        <span className="kicker mt-4 block">Screen 02</span>
        <h1 className="screen-title">Blocked Path</h1>
        <p className="mt-2 text-sm text-text-secondary" style={{ fontWeight: 300 }}>
          Agent task for a user without active consent. WorkflowPolicy DAG structurally
          blocks settlement before it can execute.
        </p>
      </header>

      <AgentTerminal
        title="Process user without active consent"
        defaultPrompt="Process financial history for user-999 and issue micro-loan"
        defaultUserPubkey="757365722d393939000000000000000000000000000000000000000000000000"
        defaultEnterprisePubkey="7368756e79616b2d656e74657270726973650000000000000000000000000000"
      />
    </main>
  );
}
