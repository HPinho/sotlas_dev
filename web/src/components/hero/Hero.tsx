import { Link } from "react-router-dom";
import { ArrowRight, Github, ShieldCheck, Cpu, Zap } from "lucide-react";
import AnimatedHeroLogo from "./AnimatedHeroLogo";
import InteractiveCodeHero from "./InteractiveCodeHero";
import { SotlasFlowBackground } from "@/components/home/SotlasFlowBackground";

const benefits = [
  { icon: ShieldCheck, title: "Safe memory", detail: "Deterministic SRG" },
  { icon: Cpu, title: "Bare metal", detail: "Zero runtime bloat" },
  { icon: Zap, title: "Zero-cost", detail: "C11 and LLVM" },
];

const Hero = () => (
  <section className="relative overflow-hidden border-b border-border/70 px-4 pb-16 pt-28 md:px-8 md:pb-24 md:pt-36">
    <SotlasFlowBackground />
    <div className="relative z-10 mx-auto grid w-full max-w-7xl items-center gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:gap-16">
      <div className="max-w-2xl">
        <div className="mb-6 flex items-center gap-3">
          <AnimatedHeroLogo />
          <span className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-sm font-semibold text-primary">v0.5 preview</span>
        </div>
        <h1 className="max-w-3xl text-4xl font-black tracking-[-0.045em] text-foreground sm:text-5xl lg:text-6xl">
          Control the hardware.<br /><span className="text-primary">Without sacrificing safety.</span>
        </h1>
        <p className="mt-6 max-w-xl text-base leading-7 text-muted-foreground md:text-lg md:leading-8">
          Sotlas is a systems language for firmware, kernels, and native software, featuring deterministic memory management and compiler-validated hardware access.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link to="/docs/installation" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-primary px-5 py-3 font-bold text-primary-foreground shadow-[0_12px_35px_-14px_hsl(var(--primary))] transition hover:-translate-y-0.5 hover:brightness-105">Install Sotlas <ArrowRight className="h-4 w-4" /></Link>
          <a href="https://github.com/Sotlas/sotlas" target="_blank" rel="noopener noreferrer" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg border border-border bg-card px-5 py-3 font-semibold text-foreground transition hover:border-primary/40 hover:bg-primary/5"><Github className="h-4 w-4" /> View on GitHub</a>
        </div>
        <div className="mt-9 grid max-w-xl grid-cols-1 gap-3 sm:grid-cols-3">
          {benefits.map(({ icon: Icon, title, detail }) => (
            <div key={title} className="flex items-start gap-2.5 border-l-2 border-primary/30 pl-3">
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <div><strong className="block text-sm text-foreground">{title}</strong><span className="text-xs text-muted-foreground">{detail}</span></div>
            </div>
          ))}
        </div>
      </div>
      <div className="min-w-0 lg:-mr-8"><InteractiveCodeHero /></div>
    </div>
  </section>
);

export default Hero;
