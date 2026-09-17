import { Link } from "react-router-dom";
import { ArrowRight, BookOpen, Terminal, Sparkles, CheckCircle2 } from "lucide-react";

export interface CategoryCardData {
  type: "docs" | "interop" | "grammar" | "changelog";
  title: string;
  description: string;
  linkText: string;
  href: string;
  badge: string;
}

export const CategoryCard = ({
  type,
  title,
  description,
  linkText,
  href,
  badge,
}: CategoryCardData) => {
  return (
    <div className="group flex flex-col justify-between h-full rounded-[2rem] overflow-hidden border border-border bg-card hover:border-primary/40 transition-all duration-300 shadow-xs hover:shadow-xl">
      {/* Live Technical Module Preview (Unified & Clean, Zero Black Image Bloat) */}
      <div className="p-4 pb-0">
        <div className="relative w-full aspect-[16/10] overflow-hidden rounded-[1.5rem] bg-muted/40 dark:bg-muted/20 border border-border/80 p-4 flex flex-col justify-between text-left font-mono text-xs">
          {/* Subtle Ambient Color Flare (zero blur) */}
          {type === "docs" && (
            <div className="absolute -top-10 -right-10 w-32 h-32 rounded-full bg-[radial-gradient(circle_at_center,rgba(249,115,22,0.15)_0%,transparent_70%)] pointer-events-none" />
          )}
          {(type === "interop" || type === "grammar") && (
            <div className="absolute -top-10 -right-10 w-32 h-32 rounded-full bg-[radial-gradient(circle_at_center,rgba(6,182,212,0.15)_0%,transparent_70%)] pointer-events-none" />
          )}
          {type === "changelog" && (
            <div className="absolute -top-10 -right-10 w-32 h-32 rounded-full bg-[radial-gradient(circle_at_center,rgba(16,185,129,0.15)_0%,transparent_70%)] pointer-events-none" />
          )}

          {/* Module Header */}
          <div className="relative z-10 flex items-center justify-between pb-2 border-b border-border/60">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-400/80 inline-block" />
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400/80 inline-block" />
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400/80 inline-block" />
              <span className="text-[11px] text-muted-foreground ml-2 font-semibold">
                {type === "docs" && "memory.sot"}
                {(type === "interop" || type === "grammar") && "cxx_bridge.sot"}
                {type === "changelog" && "release.v0.1.0"}
              </span>
            </div>

            <span className="text-[10px] px-2 py-0.5 rounded-md bg-background border border-border text-foreground font-semibold">
              {badge}
            </span>
          </div>

          {/* Module Technical Content */}
          <div className="relative z-10 my-auto py-2 text-[11px] leading-relaxed">
            {type === "docs" && (
              <div className="space-y-1.5">
                <div className="text-muted-foreground">// Zero-cost static ownership</div>
                <div className="text-foreground">
                  <span className="text-violet-600 dark:text-violet-400 font-bold">sole</span>{" "}
                  buf = Buffer.alloc(4096);
                </div>
                <div className="text-foreground">
                  <span className="text-violet-600 dark:text-violet-400 font-bold">handover</span>{" "}
                  buf <span className="text-orange-600 dark:text-orange-400 font-semibold">to</span> DmaController;
                </div>
              </div>
            )}

            {(type === "interop" || type === "grammar") && (
              <div className="space-y-1.5">
                <div className="text-muted-foreground">// Direct Clang C++ Module Ingestion</div>
                <div className="text-foreground">
                  <span className="text-cyan-600 dark:text-cyan-400 font-semibold">import</span> CxxStdlib;
                </div>
                <div className="text-foreground">
                  <span className="text-violet-600 dark:text-violet-400 font-bold">let</span> vec = std.vector&lt;u32&gt;();
                </div>
              </div>
            )}

            {type === "changelog" && (
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5 text-foreground">
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">+</span>
                  <span>Deterministic SRG verifier</span>
                </div>
                <div className="flex items-center gap-1.5 text-foreground">
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">+</span>
                  <span>.slit and .notch bus operators</span>
                </div>
                <div className="flex items-center gap-1.5 text-foreground">
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">+</span>
                  <span>Freestanding C11 backend with 0 runtime bloat</span>
                </div>
              </div>
            )}
          </div>

          {/* Module Footer Status */}
          <div className="relative z-10 pt-2 border-t border-border/60 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>Formal Validation</span>
            <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-medium">
              <CheckCircle2 className="w-3 h-3" />
              Verified
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-col gap-3 p-6 text-left">
        <div className="flex flex-col gap-1.5">
          <h3 className="text-lg font-semibold text-foreground group-hover:text-primary transition-colors">
            {title}
          </h3>
          <p className="text-xs md:text-sm text-muted-foreground leading-relaxed">
            {description}
          </p>
        </div>

        {/* CTA Link */}
        <Link
          to={href}
          className="inline-flex items-center gap-2 text-xs md:text-sm font-medium text-foreground/90 transition-colors group-hover:text-primary pt-2"
        >
          <span>{linkText}</span>
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
        </Link>
      </div>
    </div>
  );
};

export default CategoryCard;
