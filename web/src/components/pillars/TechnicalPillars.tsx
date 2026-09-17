import { Link } from "react-router-dom";
import { ArrowRight, Cpu, ShieldCheck, Binary } from "lucide-react";

const pillars = [
  {
    icon: Cpu,
    eyebrow: "Hardware",
    title: "Types that understand the machine",
    description: "Physical pointers, MMIO, DMA, and processor ports are represented in the type system — not obscured behind conventions.",
    link: "/docs/pointers",
  },
  {
    icon: ShieldCheck,
    eyebrow: "Memory",
    title: "Determinism without a garbage collector",
    description: "The Scoped Reference Graph validates ownership, transfer, and isolation at compile time, ensuring predictable zero-cost destruction.",
    link: "/docs/memory",
  },
  {
    icon: Binary,
    eyebrow: "Performance",
    title: "Native, low-level primitives",
    description: "Bits, registers, interrupts, and critical sections have dedicated syntax and compile to direct instructions without runtime bloat.",
    link: "/docs/hardware",
  },
];

export function TechnicalPillars() {
  return (
    <section className="px-4 py-20 md:px-8 md:py-28">
      <div className="mx-auto max-w-7xl">
        <div className="grid gap-8 lg:grid-cols-[0.7fr_1.3fr] lg:items-end">
          <div>
            <span className="font-mono text-sm font-semibold uppercase tracking-[0.18em] text-primary">Why Sotlas</span>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-foreground md:text-5xl">Safety down to the silicon.</h2>
          </div>
          <p className="max-w-2xl text-base leading-7 text-muted-foreground md:text-lg">
            Low-level control should never mean fragile code. Sotlas makes explicit the critical decisions that C and C++ leave to chance.
          </p>
        </div>

        <div className="mt-12 grid gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-3">
          {pillars.map(({ icon: Icon, eyebrow, title, description, link }, index) => (
            <article key={title} className="group bg-card p-6 transition-colors hover:bg-primary/[0.035] md:p-8">
              <div className="flex items-center justify-between">
                <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary"><Icon className="h-5 w-5" /></div>
                <span className="font-mono text-xs text-muted-foreground">0{index + 1}</span>
              </div>
              <span className="mt-8 block font-mono text-xs font-semibold uppercase tracking-[0.16em] text-primary">{eyebrow}</span>
              <h3 className="mt-2 text-xl font-bold tracking-tight text-foreground">{title}</h3>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">{description}</p>
              <Link to={link} className="mt-7 inline-flex items-center gap-2 text-sm font-bold text-foreground transition-colors hover:text-primary">
                Understand the concept <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export default TechnicalPillars;
