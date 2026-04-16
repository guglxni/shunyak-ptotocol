import Link from "next/link";
import { AlgorandShowcase } from "../../components/AlgorandShowcase";

export default function ShowcasePage() {
  return (
    <main>
      <header className="mb-6">
        <Link href="/" className="mono text-sm text-fog underline">
          Back to demo menu
        </Link>
        <p className="kicker mt-4">Screen 4</p>
        <h1 className="screen-title">Algorand SDK + AlgoKit Showcase</h1>
        <p className="mt-2 text-sm text-fog">
          Live snapshot from Algod/Indexer plus runtime availability checks for AlgoKit toolchain.
        </p>
      </header>

      <AlgorandShowcase />
    </main>
  );
}
