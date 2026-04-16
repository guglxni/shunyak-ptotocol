import Link from "next/link";
import { AgentTerminal } from "../../components/AgentTerminal";

export default function BlockedPage() {
  return (
    <main>
      <header className="mb-6">
        <Link href="/" className="mono text-sm text-fog underline">
          Back to demo menu
        </Link>
        <p className="kicker mt-4">Screen 2</p>
        <h1 className="screen-title">Blocked path (no consent)</h1>
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
