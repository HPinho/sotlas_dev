import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Terminal, ArrowRight, Cpu, Sparkles } from "lucide-react";
import { sotlasKeywords, KeywordItem } from "@/data/keywords";
import WaveText from "@/components/ui/wave-text";

// 6 Core Featured Keywords for the Landing Page
const featuredNames = ["sole", "*rawphys", "island", "clinch", "spec", ".slit"];
const featuredKeywords: KeywordItem[] = featuredNames
  .map((name) => sotlasKeywords.find((k) => k.name === name))
  .filter(Boolean) as KeywordItem[];

export function KeywordsGlossary() {
  return (
    <section className="px-4 md:px-8 py-10 md:py-14">
      <div className="max-w-6xl mx-auto">
        {/* Real-World Context Banner */}
        <div className="mb-10 p-4 rounded-2xl bg-card border border-border shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start sm:items-center gap-3">
            <div className="relative w-10 h-10 flex items-center justify-center shrink-0">
              <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_center,rgba(249,115,22,0.25)_0%,transparent_70%)]" />
              <img src="/icone-sotlas.svg" alt="Sotlas" className="relative z-10 w-8 h-8 object-contain" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground flex items-center gap-2">
                <span>Proven Systems Engineering: Baken OS</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 font-mono">
                  Bare-Metal
                </span>
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Used in the Baken OS kernel for direct hardware control, UEFI GOP Framebuffer, ACPI tables, and freestanding drivers.
              </p>
            </div>
          </div>
          <Link
            to="/docs/profiles"
            className="text-xs font-mono text-primary hover:underline flex items-center gap-1.5 shrink-0"
          >
            <span>Explore barecore profile</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {/* Section Header */}
        <div className="text-center mb-6 md:mb-8">
          <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-2">
            <WaveText text="Syntax Innovations & Machine Control" />
          </h2>
          <p className="text-muted-foreground text-sm max-w-xl mx-auto">
            First-class primitives designed to express deterministic memory safety and direct physical hardware access.
          </p>
        </div>

        {/* Mobile Swipe Hint */}
        <div className="flex md:hidden items-center justify-center gap-2 text-xs text-muted-foreground font-mono mb-4 px-3.5 py-1 rounded-full bg-card border border-border w-fit mx-auto">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
          <span>Swipe to view primitives</span>
          <span className="text-zinc-500 font-sans">⟷</span>
        </div>

        {/* Compact Grid of 6 Featured Keywords / Lateral Scroll on Mobile */}
        <div className="flex overflow-x-auto pb-4 pt-1 snap-x snap-mandatory scrollbar-none overscroll-x-contain -mx-4 px-4 sm:-mx-6 sm:px-6 md:mx-0 md:px-0 md:grid md:grid-cols-2 lg:grid-cols-3 gap-4 md:overflow-visible md:pb-0">
          {featuredKeywords.map((item, index) => (
            <motion.div
              key={item.name}
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.1 }}
              transition={{ duration: 0.3, delay: index * 0.06 }}
              className="p-4 rounded-2xl bg-card dark:bg-[#121316] border border-border hover:border-primary/40 transition-all flex flex-col justify-between group shadow-xs hover:shadow-md w-[80vw] max-w-[290px] shrink-0 snap-center md:w-auto md:max-w-none md:shrink"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-sm font-bold text-violet-600 dark:text-violet-300 group-hover:text-primary transition-colors bg-muted/80 px-2 py-0.5 rounded border border-border">
                    {item.name}
                  </span>
                  <span className="text-[10px] font-mono text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded border border-border/60">
                    {item.categoryLabel}
                  </span>
                </div>

                <p className="text-xs font-medium text-foreground mb-1 leading-snug">
                  {item.summary}
                </p>
                <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                  {item.description}
                </p>
              </div>

              <div className="mt-3 pt-3 border-t border-border/50">
                <pre className="p-2 rounded-lg bg-muted/50 dark:bg-muted/20 border border-border/80 font-mono text-[11px] text-emerald-600 dark:text-emerald-400 overflow-x-auto whitespace-pre">
                  <code>{item.example}</code>
                </pre>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Bottom CTA to Full Dictionary */}
        <div className="mt-8 text-center">
          <Link
            to="/docs/keywords"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium text-foreground bg-secondary hover:bg-secondary/80 border border-border transition-colors shadow-xs"
          >
            <Terminal className="w-4 h-4 text-primary" />
            <span>View Complete Dictionary (25+ Primitives)</span>
            <ArrowRight className="w-4 h-4 text-muted-foreground" />
          </Link>
        </div>
      </div>
    </section>
  );
}

export default KeywordsGlossary;
