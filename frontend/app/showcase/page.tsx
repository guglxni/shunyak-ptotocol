import Link from "next/link";
import { AlgorandShowcase } from "../../components/AlgorandShowcase";

export default function ShowcasePage() {
  return (
    <main>
      <header className="mb-8">
        <Link href="/" className="mono text-xs text-text-muted hover:text-text transition-colors">
          &larr; Back
        </Link>
        <span className="kicker mt-4 block">Screen 04</span>
        <h1 className="screen-title">Runtime Showcase</h1>
        <p className="mt-2 text-sm text-text-secondary" style={{ fontWeight: 300 }}>
          Live Algod and Indexer snapshot, AlgoKit runtime availability, signer account status,
          and engine configuration.
        </p>
      </header>

      <AlgorandShowcase />
    </main>
  );
}
