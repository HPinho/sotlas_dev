import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { HardDrive, Monitor, Globe, ArrowRight, CheckCircle2 } from "lucide-react";
import WaveText from "@/components/ui/wave-text";

const targetProfiles = [
  {
    name: "barecore",
    directive: "target barecore;",
    icon: HardDrive,
    tag: "Chip & Freestanding",
    tagColor: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/25 dark:bg-emerald-950/50 dark:border-emerald-800/60",
    headline: "Kernels, Firmware & Embedded",
    description:
      "Freestanding mode dedicated to developing kernels, drivers, bootloaders, and ultra-constrained embedded systems, operating with predictable static overhead and zero dependency on runtimes or external OS libraries.",
    features: [
      "Zero libc or OS dependency",
      "Topology Pointers (*rawphys, *portwire)",
      "Interrupt handlers with trapfn",
      "Deterministic static memory & SRG",
    ],
    codeSnippet: `target barecore;

trapfn timer_handler() {
  clinch {
    outb(0x20, 0x20); // PIC EOI
  }
  rebound;
}`,
  },
  {
    name: "native",
    directive: "target native;",
    icon: Monitor,
    tag: "Desktop & Servers",
    tagColor: "bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-500/25 dark:bg-blue-950/50 dark:border-blue-800/60",
    headline: "Services, Tools & Userland Apps",
    description:
      "Focused on backend services, CLI utilities, and userland applications taking advantage of dynamic data types, native multithreading, and high-level abstractions.",
    features: [
      "High-speed runtime with zero GC pauses",
      "Isolated concurrency with island",
      "Async I/O and standard collections",
      "Native C binary ABI compatibility",
    ],
    codeSnippet: `target native;

island Worker {
  fn process(data: Buffer) {
    // Isolated execution without data races
  }
}`,
  },
  {
    name: "web",
    directive: "target web;",
    icon: Globe,
    tag: "Browsers & Edge",
    tagColor: "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/25 dark:bg-amber-950/50 dark:border-amber-800/60",
    headline: "Web Ecosystem & WebAssembly",
    description:
      "Deploy core business logic and computational kernels directly to the web ecosystem from the same codebase, compiling to high-performance WebAssembly modules.",
    features: [
      "Direct compilation to WebAssembly",
      "Single shared codebase across targets",
      "Browser sandbox execution",
      "Zero-overhead JS/TypeScript bindings",
    ],
    codeSnippet: `target web;

export fn validate_packet(p: *virtmap Packet) -> bool {
  return p.is_valid();
}`,
  },
];

export function TargetProfiles() {
  return (
    <section className="px-4 md:px-8 py-16 md:py-24 bg-gradient-to-b from-transparent via-[#0c0d0e]/60 to-transparent relative">
      <div className="max-w-6xl mx-auto">
        {/* Section Header */}
        <div className="text-center mb-10 md:mb-14">
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-foreground tracking-tight mb-4">
            <WaveText text="Versatility via Target Profiles" />
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-2xl mx-auto leading-relaxed">
            Seamlessly adapts from bare silicon to modern desktops while preserving unified syntax and strict safety guarantees.
          </p>
        </div>

        {/* Mobile Swipe Hint */}
        <div className="flex lg:hidden items-center justify-center gap-2 text-xs text-muted-foreground font-mono mb-5 px-3.5 py-1 rounded-full bg-zinc-900/80 border border-zinc-800/80 w-fit mx-auto">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>Swipe to explore 3 profiles</span>
          <span className="text-zinc-500 font-sans">⟷</span>
        </div>

        {/* 3 Profiles Grid / Lateral Scroll on Mobile & Tablet */}
        <div className="flex overflow-x-auto pb-4 pt-1 snap-x snap-mandatory scrollbar-none overscroll-x-contain -mx-4 px-4 sm:-mx-6 sm:px-6 lg:mx-0 lg:px-0 lg:grid lg:grid-cols-3 gap-6 lg:overflow-visible lg:pb-0">
          {targetProfiles.map((target, idx) => {
            const Icon = target.icon;
            return (
              <motion.div
                key={target.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.1 }}
                transition={{ duration: 0.5, delay: idx * 0.1 }}
                className="flex flex-col justify-between p-5 sm:p-6 md:p-7 rounded-3xl bg-card dark:bg-[#101114]/90 border border-border hover:border-primary/40 transition-all duration-300 group hover:shadow-xl w-[84vw] max-w-[340px] sm:max-w-[420px] shrink-0 snap-center lg:w-auto lg:max-w-none lg:shrink"
              >
                <div>
                  {/* Card Header */}
                  <div className="flex items-center justify-between gap-2 mb-4">
                    <div className="flex items-center gap-2.5">
                      <div className="w-10 h-10 rounded-xl bg-muted/80 dark:bg-zinc-900 border border-border flex items-center justify-center group-hover:scale-105 transition-transform">
                        <Icon className="w-5 h-5 text-foreground" />
                      </div>
                      <div>
                        <code className="text-xs font-mono text-primary font-bold">
                          {target.directive}
                        </code>
                        <h3 className="text-base font-bold text-foreground">
                          {target.headline}
                        </h3>
                      </div>
                    </div>
                  </div>

                  <span
                    className={`inline-block text-[11px] font-mono px-2 py-0.5 rounded-md border mb-4 ${target.tagColor}`}
                  >
                    {target.tag}
                  </span>

                  {/* Description */}
                  <p className="text-xs md:text-sm text-muted-foreground leading-relaxed mb-5">
                    {target.description}
                  </p>

                  {/* Code Snippet */}
                  <div className="rounded-xl bg-muted/50 dark:bg-muted/20 border border-border/80 p-3 mb-5 font-mono text-xs overflow-x-auto text-foreground">
                    <pre className="text-[11px] leading-relaxed">
                      <code>{target.codeSnippet}</code>
                    </pre>
                  </div>

                  {/* Feature Bullets */}
                  <div className="space-y-2 mb-6">
                    {target.features.map((feat, fIdx) => (
                      <div key={fIdx} className="flex items-center gap-2 text-xs text-foreground/90">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />
                        <span>{feat}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <Link
                  to="/docs/profiles"
                  className="pt-4 border-t border-border/80 flex items-center justify-between text-xs font-mono text-muted-foreground hover:text-foreground transition-colors group/link"
                >
                  <span>View profile specifications</span>
                  <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover/link:translate-x-1" />
                </Link>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
export default TargetProfiles;
