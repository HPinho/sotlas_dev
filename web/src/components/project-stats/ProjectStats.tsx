import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { FlaskConical, BookOpen, Package, Shield, Scale, Cpu } from "lucide-react";
import WaveText from "@/components/ui/wave-text";

interface StatCard {
  icon: typeof FlaskConical;
  value: number;
  suffix: string;
  label: string;
  detail: string;
  color: string;
  iconBg: string;
}

const stats: StatCard[] = [
  {
    icon: FlaskConical,
    value: 298,
    suffix: "",
    label: "Unit Tests",
    detail: "Complete coverage: Lexer, Parser, Sema, SIR, Codegen, and Stdlib",
    color: "text-emerald-600 dark:text-emerald-400",
    iconBg: "bg-emerald-500/10 border-emerald-500/20",
  },
  {
    icon: BookOpen,
    value: 5,
    suffix: "",
    label: "Official Examples",
    detail: "Hello Systems, Safe Structures, Intrinsics, Raw Memory, and C/C++ Interop",
    color: "text-blue-600 dark:text-blue-400",
    iconBg: "bg-blue-500/10 border-blue-500/20",
  },
  {
    icon: Package,
    value: 12,
    suffix: "+",
    label: "Stdlib Modules",
    detail: "Implemented entirely in Sotlas: primitives, option, result, mem, arc, slice, string",
    color: "text-violet-600 dark:text-violet-400",
    iconBg: "bg-violet-500/10 border-violet-500/20",
  },
  {
    icon: Shield,
    value: 3,
    suffix: "",
    label: "Safety Layers",
    detail: "Orthogonal model: Safe Layer, @system Layer, and unsafe Boundary",
    color: "text-amber-600 dark:text-amber-400",
    iconBg: "bg-amber-500/10 border-amber-500/20",
  },
  {
    icon: Scale,
    value: 100,
    suffix: "%",
    label: "C ABI Compatible",
    detail: "Guaranteed bidirectional interoperability with C, C++, and Objective-C",
    color: "text-cyan-600 dark:text-cyan-400",
    iconBg: "bg-cyan-500/10 border-cyan-500/20",
  },
  {
    icon: Cpu,
    value: 4,
    suffix: "",
    label: "Native Targets",
    detail: "x86_64, AArch64, RISC-V, and ARM Cortex-M via freestanding C11 backend",
    color: "text-orange-600 dark:text-orange-400",
    iconBg: "bg-orange-500/10 border-orange-500/20",
  },
];

function AnimatedCounter({ target, suffix }: { target: number; suffix: string }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true;
          const duration = 1200;
          const startTime = performance.now();

          const animate = (currentTime: number) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // Ease-out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            setCount(Math.round(eased * target));
            if (progress < 1) {
              requestAnimationFrame(animate);
            }
          };

          requestAnimationFrame(animate);
        }
      },
      { threshold: 0.3 }
    );

    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [target]);

  return (
    <span ref={ref} className="tabular-nums">
      {count}{suffix}
    </span>
  );
}

export function ProjectStats() {
  return (
    <section className="px-4 md:px-8 py-16 md:py-24 relative overflow-hidden">
      <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-[radial-gradient(ellipse_at_center,rgba(139,92,246,0.05)_0%,transparent_70%)] pointer-events-none" />

      <div className="max-w-6xl mx-auto relative z-10">
        {/* Section Header */}
        <div className="text-center mb-10 md:mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-600 dark:text-violet-400 text-xs font-mono mb-3">
            <FlaskConical className="w-3.5 h-3.5" />
            <span>Project Numbers</span>
          </div>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-foreground tracking-tight mb-4">
            <WaveText text="Metrics & Guarantees" />
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-2xl mx-auto leading-relaxed">
            Every aspect of the Sotlas compiler is validated by continuous testing to ensure zero regressions.
          </p>
        </div>

        {/* GitHub Badges */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-10">
          <a href="https://github.com/Sotlas/sotlas/actions" target="_blank" rel="noopener noreferrer" className="hover:opacity-85 transition-opacity">
            <img src="https://github.com/Sotlas/sotlas/actions/workflows/ci.yml/badge.svg" alt="CI" className="h-5" />
          </a>
          <a href="https://github.com/HPinho" target="_blank" rel="noopener noreferrer" className="hover:opacity-85 transition-opacity">
            <img src="https://img.shields.io/badge/Author-Hiago%20Pinho-8b5cf6.svg" alt="Author: Hiago Pinho" className="h-5" />
          </a>
          <a href="https://github.com/Sotlas/sotlas/blob/main/LICENSE" target="_blank" rel="noopener noreferrer" className="hover:opacity-85 transition-opacity">
            <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="Apache 2.0 License" className="h-5" />
          </a>
          <img src="https://img.shields.io/badge/target-x86__64--freestanding-orange.svg" alt="Target" className="h-5" />
          <img src="https://img.shields.io/badge/architecture-SIR%20%2F%20C11%20Stage--0-green.svg" alt="Architecture" className="h-5" />
          <img src="https://img.shields.io/badge/version-0.3.0-purple.svg" alt="Version" className="h-5" />
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 md:gap-5">
          {stats.map((stat, idx) => {
            const StatIcon = stat.icon;
            return (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.1 }}
                transition={{ duration: 0.4, delay: idx * 0.08 }}
                className="rounded-2xl border border-border bg-card p-5 sm:p-6 hover:shadow-lg hover:border-primary/30 transition-all duration-300 group"
              >
                <div className={`w-10 h-10 rounded-xl ${stat.iconBg} border flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300`}>
                  <StatIcon className={`w-5 h-5 ${stat.color}`} />
                </div>
                <div className={`text-3xl sm:text-4xl font-black ${stat.color} mb-1 tracking-tight`}>
                  <AnimatedCounter target={stat.value} suffix={stat.suffix} />
                </div>
                <h4 className="text-sm font-semibold text-foreground mb-1">{stat.label}</h4>
                <p className="text-[11px] text-muted-foreground leading-relaxed">{stat.detail}</p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export default ProjectStats;
