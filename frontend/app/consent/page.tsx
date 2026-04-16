import Link from "next/link";
import { ConsentFlow } from "../../components/ConsentFlow";

export default function ConsentPage() {
  return (
    <main>
      <header className="mb-8">
        <Link href="/" className="mono text-xs text-text-muted hover:text-text transition-colors">
          &larr; Back
        </Link>
        <span className="kicker mt-4 block">Screen 01</span>
        <h1 className="screen-title">Consent Registration</h1>
        <p className="mt-2 text-sm text-text-secondary" style={{ fontWeight: 300 }}>
          Identity attestation via DigiLocker, proof generation via AlgoPlonk, and on-chain consent
          anchoring to Algorand Box Storage.
        </p>
      </header>

      <ConsentFlow />
    </main>
  );
}
