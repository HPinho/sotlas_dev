import { Link } from "react-router-dom";
import { ArrowRight, BookOpen, Terminal, Sparkles } from "lucide-react";
import WaveText from "@/components/ui/wave-text";

export function CalloutBanner() {
  return (
    <section className="px-4 md:px-8 py-16 md:py-20">
      <div className="max-w-5xl mx-auto">
        <div className="relative rounded-3xl bg-gradient-to-b from-card to-muted/40 dark:from-[#16181c] dark:to-[#0d0e10] border border-border p-6 sm:p-10 md:p-14 overflow-hidden text-center shadow-xl">
          {/* Subtle glowing radial background (zero blur) */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-96 bg-[radial-gradient(ellipse_at_center,rgba(249,115,22,0.08)_0%,transparent_70%)] pointer-events-none" />

          {/* Transparent Glowing Logo Emblem */}
          <div className="relative z-10 flex items-center justify-center w-20 h-20 mx-auto mb-6">
            <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_center,rgba(249,115,22,0.18)_0%,transparent_70%)]" />
            <img
              src="/icone-sotlas.svg"
              alt="Sotlas"
              className="relative z-10 w-16 h-16 object-contain filter drop-shadow-[0_8px_20px_rgba(249,115,22,0.3)] transition-transform hover:scale-110 duration-300"
            />
          </div>

          <h2 className="relative z-10 text-2xl md:text-4xl lg:text-5xl font-bold text-foreground tracking-tight mb-5">
            <WaveText text="From silicon to high-level applications." />
          </h2>

          <p className="relative z-10 text-muted-foreground text-sm md:text-base lg:text-lg max-w-3xl mx-auto leading-relaxed mb-8">
            Sotlas is engineered for developers who demand surgical control over memory and registers without sacrificing safety, ergonomics, or modern syntactic elegance.
          </p>

          {/* CTA Buttons */}
          <div className="relative z-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              to="/docs/overview"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-foreground text-background font-semibold text-sm hover:opacity-90 transition-opacity shadow-md"
            >
              <BookOpen className="w-4 h-4" />
              <span>Explore Documentation</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              to="/docs/interoperability"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-secondary hover:bg-secondary/80 border border-border text-foreground text-sm transition-colors font-mono shadow-2xs"
            >
              <Terminal className="w-4 h-4 text-emerald-500" />
              <span>C & C++ Interop Guide</span>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
export default CalloutBanner;
