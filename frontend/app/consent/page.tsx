import Link from "next/link";
import { ConsentFlow } from "../../components/ConsentFlow";

export default function ConsentPage() {
  return (
    <main>
      <header className="mb-6">
        <Link href="/" className="mono text-sm text-fog underline">
          Back to demo menu
        </Link>
        <p className="kicker mt-4">Screen 1</p>
        <h1 className="screen-title">Consent registration</h1>
      </header>

      <ConsentFlow />
    </main>
  );
}
