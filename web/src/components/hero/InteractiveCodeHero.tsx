import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Cpu, ShieldCheck, Layers, Play, CheckCircle2, Terminal, Copy, Check } from "lucide-react";

interface CodeExample {
  id: string;
  filename: string;
  title: string;
  badge: string;
  icon: typeof Cpu;
  code: string;
  simulatedOutput: {
    status: string;
    details: string[];
    c99Equiv?: string;
  };
}

const examples: CodeExample[] = [
  {
    id: "firmware",
    filename: "uart_driver.sot",
    title: "Direct Hardware Access",
    badge: "target barecore",
    icon: Cpu,
    code: `target barecore;

// Physical pointer validated by the compiler
let uart_base: *rawphys UInt32 = 0x1000_0000;

pub fn write_byte(byte: UInt8) {
  // Extract buffer status using native .slit operator
  clinch {
    while (uart_base.slit[5..5] == 0) {
      // Wait for FIFO to drain
    }
    uart_base.notch[0] = byte;
  }
}

trapfn uart_isr() {
  // Prologue/Epilogue guaranteed by compiler
  rebound;
}`,
    simulatedOutput: {
      status: "Freestanding Compilation Succeeded",
      details: [
        "Physical bus verification (*rawphys): OK",
        ".slit[5..5] operator optimized to BEXTR/LSR instruction",
        "clinch critical section converted to atomic interrupt mask",
        "Freestanding binary size: 148 bytes",
      ],
    },
  },
  {
    id: "srg",
    filename: "memory_pipeline.sot",
    title: "Deterministic SRG Management",
    badge: "Scoped Reference Graph",
    icon: ShieldCheck,
    code: `target native;

struct Packet {
  id: UInt32,
  payload: Buffer,
}

pub fn process_stream(source: &Stream) {
  // Zero-cost exclusive ownership (sole)
  sole packet = Packet.create(id: 101);

  // Deterministic scope transfer
  handover packet to WorkerPool;

  // Attempted reuse here would trigger a COMPILER ERROR:
  // packet.id; -> Compile Error: resource moved via handover
}`,
    simulatedOutput: {
      status: "SRG Graph Validated",
      details: [
        "Scope graph: zero orphan references or dangling pointers",
        "Static handover verified: runtime cost = 0 ns",
        "Deterministic deallocation with zero Garbage Collector pauses",
      ],
    },
  },
  {
    id: "concurrency",
    filename: "island_tasks.sot",
    title: "Race-Free Concurrency",
    badge: "island model",
    icon: Layers,
    code: `target native;

// Island guarantees isolated memory against data races
island TelemetryCollector {
  var sample_count: UInt64 = 0;

  pub fn push_metric(val: Float32) {
    sample_count += 1;
  }

  pub fn snapshot() -> UInt64 {
    return sample_count;
  }
}

pub async fn main() {
  let collector = TelemetryCollector.spawn();
  await collector.push_metric(42.5);
}`,
    simulatedOutput: {
      status: "Memory Isolation Verified",
      details: [
        "Island internal memory cannot be shared directly",
        "Communication via immutable message passing",
        "Compile-time formal prevention against race conditions",
      ],
    },
  },
];

export function InteractiveCodeHero() {
  const [activeTabId, setActiveTabId] = useState<string>("firmware");
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [showOutput, setShowOutput] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  const activeExample = examples.find((e) => e.id === activeTabId) || examples[0];

  const handleSimulate = () => {
    setIsRunning(true);
    setShowOutput(false);
    setTimeout(() => {
      setIsRunning(false);
      setShowOutput(true);
    }, 400);
  };

  const handleCopyCode = async () => {
    try {
      await navigator.clipboard.writeText(activeExample.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto rounded-xl border border-slate-700/70 bg-[#090c12] shadow-[0_30px_80px_-30px_rgba(15,23,42,0.75)] overflow-hidden text-left transition-all">
      {/* Editor Top Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between px-4 py-2.5 border-b border-slate-800 bg-[#111620] gap-2">
        {/* Window dots + Tabs */}
        <div className="flex items-center gap-3 overflow-x-auto scrollbar-none">
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="w-3 h-3 rounded-full bg-rose-500/80 inline-block" />
            <span className="w-3 h-3 rounded-full bg-amber-500/80 inline-block" />
            <span className="w-3 h-3 rounded-full bg-emerald-500/80 inline-block" />
          </div>

          <div className="flex items-center gap-1.5 shrink-0 pl-2 border-l border-border">
            {examples.map((ex) => {
              const Icon = ex.icon;
              const isActive = activeTabId === ex.id;
              return (
                <button
                  key={ex.id}
                  onClick={() => {
                    setActiveTabId(ex.id);
                    setShowOutput(false);
                  }}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-mono transition-all ${
                    isActive
                      ? "bg-slate-800 text-white font-semibold border border-slate-700"
                      : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5 text-primary" />
                  <span>{ex.filename}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between sm:justify-end gap-2 shrink-0">
          <span className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-primary/10 text-primary border border-primary/20">
            {activeExample.badge}
          </span>

          <button
            onClick={handleCopyCode}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            title="Copy code"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
          </button>

          <button
            onClick={handleSimulate}
            disabled={isRunning}
            className="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-primary text-primary-foreground text-xs font-medium hover:opacity-90 transition-all shadow-xs"
          >
            <Play className="w-3 h-3 fill-current" />
            <span>{isRunning ? "Verifying..." : "Verify SRG"}</span>
          </button>
        </div>
      </div>

      {/* Code Editor Body */}
      <div className="grid grid-cols-1 lg:grid-cols-12 bg-[#090c12] text-slate-100 transition-colors">
        <div className={`p-4 sm:p-5 font-mono text-xs sm:text-[13px] leading-relaxed overflow-x-auto ${showOutput ? "lg:col-span-7 border-b lg:border-b-0 lg:border-r border-border" : "lg:col-span-12"}`}>
          <pre className="text-slate-200">
            <code>
              {activeExample.code.split("\n").map((line, idx) => {
                // Syntax coloring helper
                const isComment = line.trim().startsWith("//");
                const isKeyword = line.includes("target") || line.includes("pub fn") || line.includes("clinch") || line.includes("trapfn") || line.includes("rebound") || line.includes("sole") || line.includes("handover") || line.includes("island") || line.includes("async") || line.includes("await");
                return (
                  <div key={idx} className="flex">
                    <span className="w-8 select-none text-muted-foreground/40 text-right pr-4 text-xs font-mono">{idx + 1}</span>
                    <span className={isComment ? "text-slate-500 italic" : isKeyword ? "text-orange-400 font-semibold" : "text-slate-200"}>
                      {line}
                    </span>
                  </div>
                );
              })}
            </code>
          </pre>
        </div>

        {/* Live Simulation Output Panel */}
        <AnimatePresence>
          {showOutput && (
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="lg:col-span-5 p-4 sm:p-5 bg-muted/30 dark:bg-[#10141e] border-t lg:border-t-0 lg:border-l border-border flex flex-col justify-between font-mono text-xs"
            >
              <div>
                <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-semibold mb-3">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  <span>{activeExample.simulatedOutput.status}</span>
                </div>

                <div className="space-y-2 mb-4">
                  {activeExample.simulatedOutput.details.map((detail, dIdx) => (
                    <div key={dIdx} className="flex items-start gap-2 text-[11px] text-foreground/80">
                      <span className="text-primary mt-0.5">›</span>
                      <span>{detail}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-3 border-t border-border text-[11px] text-muted-foreground flex items-center justify-between">
                <span>Static Determinism: 100%</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-semibold">0 memory leaks</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default InteractiveCodeHero;
