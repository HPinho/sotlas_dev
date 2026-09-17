import { motion } from "framer-motion";
import { Shield, Cpu, ArrowDown, Lock, Zap, ShieldCheck } from "lucide-react";
import WaveText from "@/components/ui/wave-text";

interface LayerData {
  name: string;
  subtitle: string;
  items: string[];
  icon: typeof Shield;
  gradient: string;
  border: string;
  iconBg: string;
}

const layers: LayerData[] = [
  {
    name: "Sotlas Safe Layer",
    subtitle: "Completely safe with zero raw pointers",
    items: ["Objects", "Arrays", "Optionals", "UI"],
    icon: Shield,
    gradient: "from-emerald-500/10 via-emerald-500/5 to-transparent",
    border: "border-emerald-500/30",
    iconBg: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  },
  {
    name: "Sotlas Systems Layer (@system)",
    subtitle: "Memory and hardware control without hidden bloat",
    items: ["*rawphys", "*portwire", "clinch", "Topology"],
    icon: Cpu,
    gradient: "from-amber-500/10 via-amber-500/5 to-transparent",
    border: "border-amber-500/30",
    iconBg: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  },
  {
    name: "Foreign FFI Layer (C / C++ / Obj-C)",
    subtitle: "Direct bidirectional C ABI call convention",
    items: ["Legacy C", "C++ Symbols", "Drivers", "POSIX libc"],
    icon: Shield,
    gradient: "from-blue-500/10 via-blue-500/5 to-transparent",
    border: "border-blue-500/30",
    iconBg: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  },
];

const transitions = [
  {
    label: "Safe Abstractions & SRG Isolation",
    color: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20",
  },
  {
    label: "Unsafe Boundary & @system capability",
    color: "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/20",
  },
];

const keyPoints = [
  {
    icon: Lock,
    title: "Rust-Style Guardrails",
    description: "Raw pointer dereferencing (*ptr) and unverified bus accesses are strictly rejected outside unsafe { ... } blocks.",
  },
  {
    icon: ShieldCheck,
    title: "Explicit FFI Boundary",
    description: "extern \"C\" bindings with raw pointers carry explicit caller risk and must be consumed inside unsafe blocks.",
  },
  {
    icon: Zap,
    title: "Zero Kernel Overhead",
    description: "No nil-messaging runtime or dynamic selector lookups. Interoperates via direct, zero-cost C ABI calling conventions.",
  },
];

export function InteropDiagram() {
  return (
    <section className="px-4 md:px-8 py-16 md:py-24 relative overflow-hidden">
      <div className="absolute bottom-0 left-1/4 w-96 h-96 bg-[radial-gradient(ellipse_at_center,rgba(245,158,11,0.05)_0%,transparent_70%)] pointer-events-none" />

      <div className="max-w-5xl mx-auto relative z-10">
        {/* Section Header */}
        <div className="text-center mb-10 md:mb-14">
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-foreground tracking-tight mb-4">
            <WaveText text="Interoperability Architecture" />
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-3xl mx-auto leading-relaxed">
            Strict orthogonal layer separation overcoming legacy language safety pitfalls without isolating into a walled garden.
          </p>
        </div>

        {/* Layers Stack */}
        <div className="max-w-2xl mx-auto mb-12">
          {layers.map((layer, idx) => {
            const LayerIcon = layer.icon;
            return (
              <div key={layer.name}>
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.2 }}
                  transition={{ duration: 0.5, delay: idx * 0.15 }}
                  className={`relative rounded-2xl border ${layer.border} bg-gradient-to-r ${layer.gradient} p-5 sm:p-6`}
                >
                  <div className="flex items-start gap-4">
                    <div className={`w-11 h-11 rounded-xl ${layer.iconBg} border border-current/10 flex items-center justify-center shrink-0`}>
                      <LayerIcon className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-base sm:text-lg font-bold text-foreground mb-1">{layer.name}</h3>
                      <p className="text-xs text-muted-foreground mb-3">{layer.subtitle}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {layer.items.map((item) => (
                          <span
                            key={item}
                            className="px-2 py-0.5 text-[10px] font-mono rounded-md bg-background/80 border border-border text-foreground/80"
                          >
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </motion.div>

                {/* Arrow + Transition Label */}
                {idx < layers.length - 1 && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.4, delay: idx * 0.15 + 0.2 }}
                    className="flex flex-col items-center py-2"
                  >
                    <ArrowDown className="w-4 h-4 text-muted-foreground/60" />
                    <span className={`mt-1 px-3 py-0.5 text-[10px] font-mono rounded-full border ${transitions[idx].color}`}>
                      {transitions[idx].label}
                    </span>
                    <ArrowDown className="w-4 h-4 text-muted-foreground/60 mt-1" />
                  </motion.div>
                )}
              </div>
            );
          })}
        </div>

        {/* Pipeline summary */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="mb-10 p-4 rounded-2xl bg-muted/30 border border-border font-mono text-xs text-center text-foreground/70 overflow-x-auto"
        >
          <span className="text-red-500">C / C++ / Obj-C</span>
          <span className="mx-2">──►</span>
          <span className="text-amber-500">[Unsafe Boundary]</span>
          <span className="mx-2">──►</span>
          <span className="text-amber-500">Sotlas Systems</span>
          <span className="mx-2">──►</span>
          <span className="text-emerald-500">[Safe Abstractions]</span>
          <span className="mx-2">──►</span>
          <span className="text-emerald-500">Sotlas Safe Layer</span>
        </motion.div>

        {/* Key Points Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {keyPoints.map((point, idx) => {
            const PointIcon = point.icon;
            return (
              <motion.div
                key={point.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.1 }}
                transition={{ duration: 0.4, delay: idx * 0.1 }}
                className="rounded-2xl border border-border bg-card p-5 shadow-xs hover:shadow-md transition-shadow"
              >
                <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-3">
                  <PointIcon className="w-5 h-5 text-primary" />
                </div>
                <h4 className="text-sm font-semibold text-foreground mb-1.5">{point.title}</h4>
                <p className="text-xs text-muted-foreground leading-relaxed">{point.description}</p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export default InteropDiagram;
