import Link from "next/link";
import { AgentTerminal } from "../../components/AgentTerminal";

export default function AuthorizedPage() {
  return (
    <main>
      <header className="mb-6">
        <Link href="/" className="mono text-sm text-fog underline">
          Back to demo menu
        </Link>
        <p className="kicker mt-4">Screen 3</p>
        <h1 className="screen-title">Authorized settlement path</h1>
        <p className="mt-2 text-sm text-fog">
          Use the same user registered in Screen 1 to see successful authorization.
        </p>
      </header>

      <AgentTerminal
        title="Process consented user and execute settlement"
        defaultPrompt="Process financial history for demo-user-001 and issue micro-loan"
        defaultUserPubkey="64656d6f2d757365722d30303100000000000000000000000000000000000000"
        defaultEnterprisePubkey="7368756e79616b2d656e74657270726973650000000000000000000000000000"
      />
    </main>
  );
}
