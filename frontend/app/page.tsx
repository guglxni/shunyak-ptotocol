import Link from "next/link";
import { LiteLLMConfigPanel } from "../components/LiteLLMConfigPanel";

const screens = [
  {
    href: "/consent",
    number: "01",
    title: "Consent Registration",
    description: "DigiLocker identity attestation, AlgoPlonk proof generation, and on-chain consent anchoring via Algorand Box Storage."
  },
  {
    href: "/blocked",
    number: "02",
    title: "Blocked Agent Path",
    description: "Execute an agent task without valid consent. WorkflowPolicy DAG structurally blocks settlement."
  },
  {
    href: "/authorized",
    number: "03",
    title: "Authorized Settlement",
    description: "Execute the same task with active consent. Agent proceeds through compliance verification to settlement."
  },
  {
    href: "/showcase",
    number: "04",
    title: "Runtime Showcase",
    description: "Live Algorand SDK metrics, AlgoKit runtime state, signer account status, and engine configuration."
  }
] as const;

export default function HomePage() {
  return (
    <main>
      <section className="py-12">
        <div className="pill mono mb-6">Algorand TestNet  /  App 758909516</div>
        <h1 className="text-4xl font-700 tracking-tight md:text-5xl" style={{ fontWeight: 700, letterSpacing: "-0.03em" }}>
          Shunyak Protocol
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-text-secondary" style={{ fontWeight: 300 }}>
          DPDP-native consent governance for autonomous agents. Structural tool-order enforcement
          ensures settlement is blocked unless compliance verification succeeds against on-chain consent state.
        </p>
        <div className="mt-6 flex gap-3">
          <span className="pill mono">AlgoKit 4.0</span>
          <span className="pill mono">DigiLocker</span>
          <span className="pill mono">AlgoPlonk ZK</span>
        </div>
      </section>

      <div className="h-px bg-border" />

      <section className="mt-8 grid gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-2">
        {screens.map((screen) => (
          <Link
            key={screen.href}
            href={screen.href}
            className="group bg-bg-card p-6 transition-colors hover:bg-[#18181b]"
          >
            <span className="mono text-xs text-text-muted">{screen.number}</span>
            <h2 className="mt-2 text-lg font-600" style={{ fontWeight: 600 }}>{screen.title}</h2>
            <p className="mt-2 text-sm text-text-secondary" style={{ fontWeight: 300 }}>{screen.description}</p>
            <span className="mono mt-4 inline-block text-xs text-text-muted transition-colors group-hover:text-text">
              Open &rarr;
            </span>
          </Link>
        ))}
      </section>

      <LiteLLMConfigPanel />

      <footer className="mt-12 border-t border-border pt-6">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-text-muted">
          <span className="mono">AlgoBharat Hack Series 3.0</span>
          <span className="mono">Round 2 MVP</span>
          <span className="mono">Vercel + Algorand TestNet</span>
        </div>
      </footer>
    </main>
  );
}
