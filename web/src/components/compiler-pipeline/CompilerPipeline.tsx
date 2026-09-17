import { useState } from "react";
import { motion } from "framer-motion";
import { FileCode, Cpu, ShieldCheck, Binary, ArrowRight, Zap, CheckCircle2 } from "lucide-react";
import WaveText from "@/components/ui/wave-text";

interface PipelineStage {
  step: string;
  title: string;
  badge: string;
  icon: typeof FileCode;
  description: string;
  outputPreview: string;
  color: string;
}

const stages: PipelineStage[] = [
  {
    step: "01",
    title: "Sotlas Frontend",
    badge: ".sot Source",
    icon: FileCode,
    description: "Deterministic lexing and parsing with zero header files and no obscure preprocessor macros.",
    outputPreview: "Typed AST with 'spec' and 'adopts' contracts",
    color: "text-amber-500 border-amber-500/30 bg-amber-500/10",
  },
  {
    step: "02",
    title: "SRG & Topology Engine",
    badge: "Static Verification",
    icon: ShieldCheck,
    description: "The Scoped Reference Graph (SRG) proves zero leaks and validates physical machine buses (*rawphys).",
    outputPreview: "Validated acyclic static ownership graph (0 runtime cost)",
    color: "text-emerald-500 border-emerald-500/30 bg-emerald-500/10",
  },
  {
    step: "03",
    title: "Optimization & Emission",
    badge: "C99 / LLVM IR",
    icon: Cpu,
    description: "Emits portable freestanding C99 compatible with any microcontroller or outputs native LLVM IR.",
    outputPreview: "Optimized bitwise instructions (.slit -> BEXTR)",
    color: "text-cyan-500 border-cyan-500/30 bg-cyan-500/10",
  },
  {
    step: "04",
    title: "Final Artifact",
    badge: "Bare-Metal / Native",
    icon: Binary,
    description: "Lean final binary with no heavy runtime, no garbage collector, ready for bootloaders, firmware, or desktop.",
    outputPreview: "ELF, UEFI BOOTX64.EFI, WASM, or OS Binary",
    color: "text-violet-500 border-violet-500/30 bg-violet-500/10",
  },
];

export function CompilerPipeline() {
  const [selectedStage, setSelectedStage] = useState<number>(1);

  return (
    <section className="relative px-4 md:px-8 py-16 md:py-24">
      <div className="max-w-6xl mx-auto">
        {/* Section Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-mono mb-3">
            <Zap className="w-3.5 h-3.5" />
            <span>Compiler Architecture</span>
          </div>
          <h2 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight mb-3">
            <WaveText text="How Sotlas Compiles" />
          </h2>
          <p className="text-muted-foreground text-sm md:text-base max-w-2xl mx-auto">
            Mathematical ownership proofs and hardware bus validation before emitting a single byte of machine code.
          </p>
        </div>

        {/* 4 Steps Horizontal Flow */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {stages.map((stage, idx) => {
            const Icon = stage.icon;
            const isSelected = selectedStage === idx;
            return (
              <motion.div
                key={stage.step}
                onClick={() => setSelectedStage(idx)}
                whileHover={{ y: -3 }}
                transition={{ duration: 0.2 }}
                className={`cursor-pointer rounded-2xl p-5 border transition-all flex flex-col justify-between ${
                  isSelected
                    ? "bg-card border-primary/50 shadow-md ring-1 ring-primary/30"
                    : "bg-card/70 hover:bg-card border-border hover:border-border/80 shadow-2xs"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="font-mono text-xs font-bold text-muted-foreground">
                      STEP {stage.step}
                    </span>
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded-md border ${stage.color}`}>
                      {stage.badge}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-muted/60 border border-border flex items-center justify-center">
                      <Icon className="w-5 h-5 text-foreground" />
                    </div>
                    <h3 className="font-bold text-base text-foreground">
                      {stage.title}
                    </h3>
                  </div>

                  <p className="text-xs text-muted-foreground leading-relaxed mb-4">
                    {stage.description}
                  </p>
                </div>

                <div className="pt-3 border-t border-border/60 flex items-center justify-between text-[11px] font-mono text-foreground/80">
                  <span className="truncate">{stage.outputPreview}</span>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 ml-1.5" />
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Informative Callout */}
        <div className="rounded-2xl border border-border bg-card p-5 sm:p-6 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-xs">
          <div className="flex items-center gap-3.5 text-left">
            <div className="w-11 h-11 rounded-xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center shrink-0">
              <Zap className="w-5 h-5 text-orange-500" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-foreground">
                Complete Freestanding Compatibility
              </h4>
              <p className="text-xs text-muted-foreground mt-0.5">
                The compilation backend emits strict C99 with zero libc dependencies, targeting x86_64, AArch64, RISC-V, and ARM Cortex-M.
              </p>
            </div>
          </div>

          <a
            href="/docs/compiler"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium text-foreground bg-secondary hover:bg-secondary/80 border border-border transition-colors whitespace-nowrap"
          >
            <span>Explore Compiler Pipeline</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>
    </section>
  );
}

export default CompilerPipeline;
