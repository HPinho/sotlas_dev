import { motion } from "framer-motion";
import { AlertTriangle, XCircle, ShieldOff, Bug, Puzzle, Layers, Gauge, Skull } from "lucide-react";
import WaveText from "@/components/ui/wave-text";

interface LegacyGap {
  icon: typeof AlertTriangle;
  title: string;
  description: string;
}

interface LegacyLanguage {
  name: string;
  subtitle: string;
  accentColor: string;
  badgeBg: string;
  borderColor: string;
  gaps: LegacyGap[];
}

const languages: LegacyLanguage[] = [
  {
    name: "C",
    subtitle: "Trade-offs in established systems languages",
    accentColor: "text-red-500 dark:text-red-400",
    badgeBg: "bg-red-500/10 text-red-700 dark:text-red-300 border-red-500/25",
    borderColor: "border-red-500/20 hover:border-red-500/40",
    gaps: [
      {
        icon: ShieldOff,
        title: "Lack of Memory Safety",
        description: "Unrestricted raw pointer access yields buffer overflows, use-after-free, and dangling pointers.",
      },
      {
        icon: Puzzle,
        title: "Absence of Modules",
        description: "Fragile textual preprocessor dependency (#include), susceptible to global name collisions and macro leakage.",
      },
      {
        icon: Bug,
        title: "Fragile Error Handling",
        description: "Manual magic return integers (-1, NULL), frequently ignored by application developers.",
      },
      {
        icon: XCircle,
        title: "Explicit low-level boundaries",
        description: "Sotlas explores syntax for describing system boundaries; validated physical hardware access remains future work.",
      },
    ],
  },
  {
    name: "C++",
    subtitle: "Different language designs make different trade-offs",
    accentColor: "text-blue-500 dark:text-blue-400",
    badgeBg: "bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-500/25",
    borderColor: "border-blue-500/20 hover:border-blue-500/40",
    gaps: [
      {
        icon: Layers,
        title: "Excessive Complexity",
        description: "Massive specifications, template meta-programming that blows up compile times and binary sizes.",
      },
      {
        icon: Skull,
        title: "Runtime and target choices",
        description: "C++ supports many deployment models. Sotlas is exploring a narrower systems programming model in its current preview.",
      },
      {
        icon: AlertTriangle,
        title: "ABI Nightmare",
        description: "Lack of a stable cross-compiler, cross-version ABI standard.",
      },
    ],
  },
  {
    name: "Objective-C",
    subtitle: "A different runtime and object model",
    accentColor: "text-orange-500 dark:text-orange-400",
    badgeBg: "bg-orange-500/10 text-orange-700 dark:text-orange-300 border-orange-500/25",
    borderColor: "border-orange-500/20 hover:border-orange-500/40",
    gaps: [
      {
        icon: Gauge,
        title: "Dynamic Dispatch Overhead",
        description: "Dynamic message sending via runtime (objc_msgSend) imposes prohibitive costs on tight loops.",
      },
      {
        icon: Bug,
        title: "Bug-Masking Behavior",
        description: "Sending messages to nil silently masks severe runtime logic flaws that should fail fast.",
      },
      {
        icon: XCircle,
        title: "Different interoperability model",
        description: "Objective-C has a mature dynamic runtime. Sotlas focuses on statically checked source and a limited C ABI subset.",
      },
    ],
  },
];

export function WhySotlas() {
  return (
    <section className="px-4 md:px-8 py-16 md:py-24 relative overflow-hidden">
      {/* Background glow (zero blur) */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-3/4 h-96 bg-[radial-gradient(ellipse_at_center,rgba(239,68,68,0.05)_0%,transparent_70%)] pointer-events-none" />

      <div className="max-w-6xl mx-auto relative z-10">
        {/* Section Header */}
        <div className="text-center mb-10 md:mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-xs font-mono mb-3">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Historical Gaps</span>
          </div>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-foreground tracking-tight mb-4">
            <WaveText text="Why Sotlas?" />
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-3xl mx-auto leading-relaxed">
            Systems languages make different trade-offs in safety, runtime behavior, interoperability, and target support.
          </p>
        </div>

        {/* Mobile Swipe Hint */}
        <div className="flex md:hidden items-center justify-center gap-2 text-xs text-muted-foreground font-mono mb-5 px-3.5 py-1 rounded-full bg-card border border-border w-fit mx-auto">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
          <span>Swipe to explore languages</span>
          <span className="text-muted-foreground font-sans">⟷</span>
        </div>

        {/* Language Cards */}
        <div className="flex overflow-x-auto pb-4 pt-1 snap-x snap-mandatory scrollbar-none overscroll-x-contain -mx-4 px-4 sm:-mx-6 sm:px-6 md:mx-0 md:px-0 md:grid md:grid-cols-3 gap-5 lg:gap-6 md:overflow-visible md:pb-0">
          {languages.map((lang, idx) => (
            <motion.div
              key={lang.name}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.1 }}
              transition={{ duration: 0.5, delay: idx * 0.12 }}
              className={`group relative flex flex-col p-5 sm:p-7 rounded-3xl bg-card dark:bg-[#0f1012] border ${lang.borderColor} transition-all duration-300 hover:shadow-xl dark:hover:shadow-black/50 w-[84vw] max-w-[340px] sm:max-w-[420px] shrink-0 snap-center md:w-auto md:max-w-none md:shrink`}
            >
              {/* Language Name + Badge */}
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                  <div className={`text-3xl font-black ${lang.accentColor} font-mono`}>
                    {lang.name}
                  </div>
                </div>
                <span className={`text-[10px] font-mono px-2.5 py-1 rounded-full border ${lang.badgeBg}`}>
                  Legacy
                </span>
              </div>

              <p className="text-xs text-muted-foreground mb-5 font-medium">{lang.subtitle}</p>

              {/* Gaps List */}
              <div className="space-y-3.5 flex-1">
                {lang.gaps.map((gap, gapIdx) => {
                  const GapIcon = gap.icon;
                  return (
                    <div key={gapIdx} className="flex items-start gap-3 p-3 rounded-xl bg-muted/40 dark:bg-zinc-900/60 border border-border/50">
                      <div className="w-8 h-8 rounded-lg bg-red-500/10 border border-red-500/15 flex items-center justify-center shrink-0 mt-0.5">
                        <GapIcon className="w-4 h-4 text-red-500 dark:text-red-400" />
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-foreground/90 mb-0.5">{gap.title}</h4>
                        <p className="text-[11px] text-muted-foreground leading-relaxed">{gap.description}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          ))}
        </div>

        {/* Bottom callout */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="mt-10 text-center"
        >
          <p className="text-sm text-muted-foreground max-w-2xl mx-auto">
            Sotlas is an experimental language exploring explicit ownership and systems-oriented syntax. The current release scope describes what the compiler can validate today.
          </p>
        </motion.div>
      </div>
    </section>
  );
}

export default WhySotlas;
