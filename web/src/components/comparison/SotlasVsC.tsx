import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Check, X, ArrowRight, ShieldCheck, Cpu, Code2, AlertTriangle } from "lucide-react";
import WaveText from "@/components/ui/wave-text";

const comparisonItems = [
  {
    title: "Memory Model & Ownership",
    sotlas: "Deterministic SRG graph (sole, co-owned, island) with handover and quarantine built directly into the type system.",
    cLang: "Unchecked static, stack, and manual heap allocation (malloc/free prone to memory leaks and double-frees).",
    sotlasAdvantage: true,
  },
  {
    title: "Topology Pointers",
    sotlas: "Physiographic typing (*rawphys, *virtmap, *portwire, *dmazone). The compiler prevents mixing incompatible hardware buses.",
    cLang: "Generic raw pointers (T* and void*). Any pointer accepts arbitrary addresses without physical validation.",
    sotlasAdvantage: true,
  },
  {
    title: "Bounded Types",
    sotlas: "Native PrimitiveType.bound[min..max] syntax. Range violations are rejected at compile time.",
    cLang: "Nonexistent. Requires manual runtime bounds-checks susceptible to overflow and cast truncation errors.",
    sotlasAdvantage: true,
  },
  {
    title: "Critical Sections & Hardware",
    sotlas: "Structured clinch/revert instructions with guaranteed atomic interrupt state restoration and quench cleanup.",
    cLang: "Relies on fragile macros and loose inline assembly (cli/sti) without stack unwinding or restoration guarantees.",
    sotlasAdvantage: true,
  },
  {
    title: "Native Bit Manipulation",
    sotlas: "Dedicated .slit[lo..hi], .notch[n], and .strand operators (native single-instruction bswap).",
    cLang: "Manual binary masks and bitwise shifts prone to operator precedence and signedness bugs.",
    sotlasAdvantage: true,
  },
  {
    title: "API Contracts",
    sotlas: "spec and adopts statically validated in the AST. Zero header files (.h or .hpp) required.",
    cLang: "Fragile .h/.c split relying on blind textual preprocessor file inclusion (#include).",
    sotlasAdvantage: true,
  },
];

export function SotlasVsC() {
  return (
    <section className="px-4 md:px-8 py-12 md:py-16 relative">
      <div className="max-w-6xl mx-auto">
        {/* Section Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-xs font-mono text-emerald-400 mb-3">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Fundamental Semantic Differences</span>
          </div>
          <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-3">
            <WaveText text="Sotlas is not merely C with alternative syntax" />
          </h2>
          <p className="text-muted-foreground text-sm md:text-base max-w-2xl mx-auto">
            While the initial bootstrap compiler generates freestanding C11 as a portable backend, Sotlas's safety guarantees and type system impose strict invariants that C completely lacks.
          </p>
        </div>

        {/* Mobile Swipe Hint */}
        <div className="flex md:hidden items-center justify-center gap-2 text-xs text-muted-foreground font-mono mb-4 px-3.5 py-1 rounded-full bg-zinc-900/80 border border-zinc-800/80 w-fit mx-auto">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>Swipe to compare</span>
          <span className="text-zinc-500 font-sans">⟷</span>
        </div>

        {/* Comparison Grid / Lateral Scroll on Mobile */}
        <div className="flex overflow-x-auto pb-4 pt-1 snap-x snap-mandatory scrollbar-none overscroll-x-contain -mx-4 px-4 sm:-mx-6 sm:px-6 md:mx-0 md:px-0 md:grid md:grid-cols-2 lg:grid-cols-3 gap-4 mb-10 md:overflow-visible md:pb-0">
          {comparisonItems.map((item, index) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.1 }}
              transition={{ duration: 0.4, delay: index * 0.08 }}
              className="p-5 rounded-2xl bg-card border border-border flex flex-col justify-between shadow-xs hover:shadow-md transition-all w-[84vw] max-w-[320px] shrink-0 snap-center md:w-auto md:max-w-none md:shrink"
            >
              <div>
                <h3 className="font-semibold text-sm text-foreground mb-3 flex items-center justify-between">
                  <span>{item.title}</span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border">
                    Sotlas vs C
                  </span>
                </h3>

                {/* Sotlas side */}
                <div className="mb-3 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                  <div className="flex items-center gap-1.5 text-xs font-mono font-semibold text-emerald-600 dark:text-emerald-400 mb-1">
                    <Check className="w-3.5 h-3.5" />
                    <span>In Sotlas</span>
                  </div>
                  <p className="text-xs text-foreground/90 leading-relaxed">
                    {item.sotlas}
                  </p>
                </div>

                {/* C side */}
                <div className="p-3 rounded-xl bg-muted/50 border border-border">
                  <div className="flex items-center gap-1.5 text-xs font-mono text-muted-foreground mb-1">
                    <X className="w-3.5 h-3.5 text-muted-foreground" />
                    <span>In Traditional C</span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {item.cLang}
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Lowering / Compiler Architecture Callout */}
        <div className="p-5 md:p-6 rounded-2xl bg-zinc-900/70 border border-zinc-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 flex-shrink-0 mt-1 md:mt-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-foreground mb-1">
                Compiling to C does not make the language C
              </h4>
              <p className="text-xs text-zinc-400 leading-relaxed max-w-3xl">
                Much like other modern systems compilers that use C or LLVM IR as an emission vehicle, the Sotlas compiler strictly validates and rejects invalid states during semantic and SRG passes before any code is emitted. The resulting C11 code is simply a portable bootstrap artifact.
              </p>
            </div>
          </div>
          <Link
            to="/docs/compiler"
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-medium text-foreground bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 transition-colors flex-shrink-0"
          >
            <span>View complete compiler analysis</span>
            <ArrowRight className="w-3.5 h-3.5 text-primary" />
          </Link>
        </div>
      </div>
    </section>
  );
}

export default SotlasVsC;
