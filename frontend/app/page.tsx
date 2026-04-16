import Link from "next/link";

const cards = [
  {
    href: "/consent",
    title: "Screen 1: Consent Registration",
    description: "Generate zkTLS-style claim proof and register consent using real TestNet note tx when funded."
  },
  {
    href: "/blocked",
    title: "Screen 2: Blocked Agent Path",
    description: "Run agent task for a user without consent and observe structural block."
  },
  {
    href: "/authorized",
    title: "Screen 3: Authorized Settlement Path",
    description: "Run the same task for consented user and watch settlement authorization."
  },
  {
    href: "/showcase",
    title: "Screen 4: SDK and Kit Showcase",
    description: "Inspect live Algorand SDK metrics and AlgoKit runtime availability."
  }
] as const;

export default function HomePage() {
  return (
    <main>
      <section className="panel p-8 md:p-12">
        <p className="kicker">Shunyak Protocol</p>
        <h1 className="screen-title">DPDP-native consent governance for autonomous agents</h1>
        <p className="mt-5 max-w-3xl text-fog">
          This MVP demonstrates structural tool-order enforcement: settlement is blocked unless
          compliance verification succeeds against consent state.
        </p>
        <div className="mt-6 status-pill mono">Deployment target: Vercel + Algorand Testnet</div>
      </section>

      <section className="mt-7 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="panel group p-6 transition-transform duration-200 hover:-translate-y-1 hover:shadow-glow"
          >
            <p className="kicker">Demo Route</p>
            <h2 className="mt-2 text-xl font-semibold text-paper">{card.title}</h2>
            <p className="mt-3 text-sm text-fog">{card.description}</p>
            <p className="mono mt-6 text-sm text-moss group-hover:text-ember">Open route -&gt;</p>
          </Link>
        ))}
      </section>
    </main>
  );
}
