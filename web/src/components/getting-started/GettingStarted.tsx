import { useState } from "react";
import { motion } from "framer-motion";
import { Terminal, Copy, Check, ArrowRight, Rocket, BookOpen } from "lucide-react";
import { Link } from "react-router-dom";
import WaveText from "@/components/ui/wave-text";

interface CliCommand {
  label: string;
  description: string;
  command: string;
}

const installSteps = [
  { step: "1", label: "Clone the repository", command: "git clone https://github.com/Sotlas/sotlas.git" },
  { step: "2", label: "Enter directory", command: "cd sotlas" },
  { step: "3", label: "Install in editable mode", command: "pip install -e ." },
];

const cliCommands: CliCommand[] = [
  { label: "sotlas version", description: "Display language version", command: "sotlas version" },
  { label: "sotlas check", description: "Validate syntax, types, and safety", command: "sotlas check examples/01_hello_systems/main.sotlas" },
  { label: "sotlas dump-ast", description: "Inspect parsed AST", command: "sotlas dump-ast examples/01_hello_systems/main.sotlas" },
  { label: "sotlas dump-sir", description: "Inspect SSA SIR", command: "sotlas dump-sir examples/01_hello_systems/main.sotlas" },
  { label: "sotlas compile", description: "Emit intermediate C11 code", command: "sotlas compile examples/01_hello_systems/main.sotlas --emit-c" },
  { label: "sotlas test", description: "Execute test suite", command: "sotlas test" },
];

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* noop */ }
  };

  return (
    <button
      onClick={handleCopy}
      className="p-1.5 rounded-lg text-muted-foreground/60 hover:text-foreground hover:bg-white/10 transition-colors"
      title="Copy"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

export function GettingStarted() {
  return (
    <section className="px-4 md:px-8 py-16 md:py-24 relative overflow-hidden">
      <div className="absolute top-0 left-1/3 w-96 h-96 bg-[radial-gradient(ellipse_at_center,rgba(6,182,212,0.05)_0%,transparent_70%)] pointer-events-none" />

      <div className="max-w-5xl mx-auto relative z-10">
        {/* Section Header */}
        <div className="text-center mb-10 md:mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-600 dark:text-cyan-400 text-xs font-mono mb-3">
            <Rocket className="w-3.5 h-3.5" />
            <span>Quickstart</span>
          </div>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-foreground tracking-tight mb-4">
            <WaveText text="Get Started in 3 Steps" />
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-2xl mx-auto leading-relaxed">
            From repository clone to your first verified Sotlas build in under 2 minutes.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Installation Terminal */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ duration: 0.5 }}
            className="rounded-3xl border border-border overflow-hidden shadow-xl"
          >
            {/* Terminal Title Bar */}
            <div className="flex items-center justify-between px-4 py-2.5 bg-zinc-900 dark:bg-zinc-950 border-b border-zinc-800">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-rose-500/80" />
                <span className="w-3 h-3 rounded-full bg-amber-500/80" />
                <span className="w-3 h-3 rounded-full bg-emerald-500/80" />
              </div>
              <span className="text-[11px] font-mono text-zinc-500">Terminal — Installation</span>
              <div className="w-14" />
            </div>

            {/* Terminal Body */}
            <div className="bg-zinc-950 dark:bg-[#0a0a0f] p-5 font-mono text-sm space-y-4">
              {installSteps.map((step) => (
                <div key={step.step}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-zinc-600 uppercase tracking-wider">
                      Step {step.step} — {step.label}
                    </span>
                    <CopyButton text={step.command} />
                  </div>
                  <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-900/80 border border-zinc-800/60">
                    <span className="text-emerald-400 shrink-0">$</span>
                    <span className="text-zinc-200 break-all">{step.command}</span>
                  </div>
                </div>
              ))}

              {/* Success line */}
              <div className="pt-2 border-t border-zinc-800/60 flex items-center gap-2 text-xs text-emerald-400">
                <Check className="w-3.5 h-3.5" />
                <span>Ready! Run <code className="text-amber-400">sotlas version</code> to confirm.</span>
              </div>
            </div>
          </motion.div>

          {/* CLI Commands Reference */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="rounded-3xl border border-border bg-card overflow-hidden shadow-xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-border bg-muted/40">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-primary" />
                <span className="text-sm font-semibold text-foreground">Driver CLI Commands</span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-primary/10 text-primary border border-primary/20">
                sotlas
              </span>
            </div>

            {/* Commands List */}
            <div className="p-4 space-y-2">
              {cliCommands.map((cmd) => (
                <div key={cmd.label} className="group rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/40 transition-colors p-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-semibold text-foreground">{cmd.description}</span>
                    <CopyButton text={cmd.command} />
                  </div>
                  <code className="block text-[11px] font-mono text-primary/90 bg-background/60 px-2.5 py-1.5 rounded-lg border border-border/50 break-all">
                    {cmd.command}
                  </code>
                </div>
              ))}
            </div>

            {/* Footer CTA */}
            <div className="px-5 py-3.5 border-t border-border bg-muted/20 flex items-center justify-between">
              <span className="text-[11px] text-muted-foreground font-mono">Unified driver for the full lifecycle</span>
              <Link
                to="/docs/installation"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:text-primary/80 transition-colors"
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Full Guide</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

export default GettingStarted;
