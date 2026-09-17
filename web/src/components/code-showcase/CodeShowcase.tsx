import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Play, Pause, RotateCcw, Terminal, Cpu, Layers, Sparkles, CheckCircle2, ShieldAlert } from "lucide-react";
import { codeScenarios, CodeScenario } from "./codeShowcaseData";
import WaveText from "@/components/ui/wave-text";

interface CodeShowcaseProps {
  embedded?: boolean;
}

export function CodeShowcase({ embedded = false }: CodeShowcaseProps) {
  const [activeScenarioId, setActiveScenarioId] = useState<string>(codeScenarios[0].id);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [loopCount, setLoopCount] = useState<number>(1);
  const terminalLogsRef = useRef<HTMLDivElement>(null);

  const scenario: CodeScenario = codeScenarios.find((s) => s.id === activeScenarioId) || codeScenarios[0];

  // Reset steps when scenario changes
  useEffect(() => {
    setCurrentStepIndex(0);
    setLoopCount(1);
  }, [activeScenarioId]);

  // Real-time loop ticker
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentStepIndex((prevIndex) => {
        if (prevIndex + 1 < scenario.logs.length) {
          return prevIndex + 1;
        } else {
          // Loop restart
          setLoopCount((c) => c + 1);
          return 0;
        }
      });
    }, 1100);

    return () => clearInterval(interval);
  }, [isPlaying, scenario.logs.length]);

  // Auto-scroll terminal log
  useEffect(() => {
    if (terminalLogsRef.current) {
      terminalLogsRef.current.scrollTop = terminalLogsRef.current.scrollHeight;
    }
  }, [currentStepIndex]);

  const visibleLogs = scenario.logs.slice(0, currentStepIndex + 1);

  // Simple syntax tokenizer for Sotlas code lines
  const renderCodeLine = (line: string, index: number) => {
    // Check if line is a comment
    if (line.trim().startsWith("//")) {
      return <span className="text-zinc-500 italic">{line}</span>;
    }

    // Highlighting rules for Sotlas keywords
    const keywords = [
      "target", "barecore", "native", "web", "module", "pub", "import", "spec",
      "struct", "class", "mesh", "adopts", "sole", "island", "quarantine", "handover",
      "clinch", "revert", "quench", "gate", "guard", "else", "rebound", "align",
      "fn", "async", "await", "init", "deinit", "let", "var", "return", "self", "super"
    ];

    const types = [
      "UInt8", "UInt16", "UInt32", "UInt64", "Int", "Int32", "Int64", "Float32",
      "Float64", "Bool", "String", "Void", "*rawphys", "*virtmap", "*portwire",
      "*dmazone", "*voidzero", "bound", "mut"
    ];

    const tokens = line.split(/(\s+|[(),;:{}[\]=><|&!+*?])/);

    return (
      <span key={index}>
        {tokens.map((token, tIdx) => {
          if (keywords.includes(token)) {
            return (
              <span key={tIdx} className="text-violet-400 font-semibold">
                {token}
              </span>
            );
          }
          if (types.includes(token) || token.startsWith("*")) {
            return (
              <span key={tIdx} className="text-emerald-400 font-medium">
                {token}
              </span>
            );
          }
          if (token.startsWith(".slit") || token.startsWith(".notch") || token.startsWith(".strand")) {
            return (
              <span key={tIdx} className="text-cyan-300 font-semibold">
                {token}
              </span>
            );
          }
          if (/^0x[0-9A-Fa-f]+$/.test(token) || /^[0-9]+$/.test(token)) {
            return (
              <span key={tIdx} className="text-amber-300">
                {token}
              </span>
            );
          }
          if (token.startsWith('"') || token.endsWith('"')) {
            return (
              <span key={tIdx} className="text-emerald-300">
                {token}
              </span>
            );
          }
          return <span key={tIdx}>{token}</span>;
        })}
      </span>
    );
  };

  return (
    <div className={embedded ? "w-full my-8" : "px-4 md:px-8 py-12 md:py-16 relative"}>
      <div className={embedded ? "w-full" : "max-w-6xl mx-auto"}>
        {/* Section Header */}
        {!embedded && (
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-xs font-mono text-primary mb-3">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Sotlas Unified Engine — Live Demonstration</span>
            </div>
            <h2 className="text-2xl md:text-4xl font-bold text-foreground tracking-tight mb-3">
              <WaveText text="From Low-Level Hardware to High-Level Expressiveness" />
            </h2>
            <p className="text-muted-foreground text-sm md:text-base max-w-2xl mx-auto">
              See Sotlas syntax in continuous execution. Switch between low-level hardware profiles and high-level services with SRG memory safety.
            </p>
          </div>
        )}

        {/* Scenario Tabs */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-6">
          {codeScenarios.map((sc) => {
            const isActive = sc.id === activeScenarioId;
            return (
              <button
                key={sc.id}
                onClick={() => setActiveScenarioId(sc.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? "bg-zinc-800 text-foreground border border-zinc-700 shadow-md"
                    : "bg-zinc-900/60 text-muted-foreground hover:text-foreground hover:bg-zinc-800/50 border border-border"
                }`}
              >
                {sc.id === "barecore" ? (
                  <Cpu className={`w-4 h-4 ${isActive ? "text-cyan-400" : ""}`} />
                ) : sc.id === "native-srg" ? (
                  <Layers className={`w-4 h-4 ${isActive ? "text-violet-400" : ""}`} />
                ) : (
                  <Terminal className={`w-4 h-4 ${isActive ? "text-amber-400" : ""}`} />
                )}
                <span>{sc.title}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-950/60 text-zinc-400 border border-zinc-800">
                  {sc.levelBadge}
                </span>
              </button>
            );
          })}
        </div>

        {/* Main Grid: Code Editor on Left, Live Simulator on Right */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
          {/* Left Column: Code Editor (7 cols) */}
          <div className="lg:col-span-7 flex flex-col rounded-2xl border border-border bg-card dark:bg-[#0F1012] overflow-hidden shadow-sm">
            {/* Editor Header Bar */}
            <div className="flex items-center justify-between px-4 py-3 bg-muted/60 dark:bg-[#151619] border-b border-border">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-red-500/80 inline-block" />
                <span className="w-3 h-3 rounded-full bg-yellow-500/80 inline-block" />
                <span className="w-3 h-3 rounded-full bg-green-500/80 inline-block" />
                <span className="ml-2 text-xs font-mono text-muted-foreground">{scenario.filename}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-muted text-foreground border border-border">
                  {scenario.profile}
                </span>
              </div>
            </div>

            {/* Code Body */}
            <div className="p-4 font-mono text-xs md:text-[13px] leading-relaxed overflow-x-auto text-foreground flex-1">
              <pre className="whitespace-pre">
                {scenario.code.split("\n").map((line, idx) => (
                  <div key={idx} className="table-row">
                    <span className="table-cell pr-4 text-right select-none text-muted-foreground/40 w-8">
                      {idx + 1}
                    </span>
                    <span className="table-cell">{renderCodeLine(line, idx)}</span>
                  </div>
                ))}
              </pre>
            </div>

            {/* Editor Footer / Info */}
            <div className="px-4 py-2.5 bg-muted/40 dark:bg-[#121316] border-t border-border text-[11px] text-muted-foreground flex items-center justify-between">
              <span>{scenario.subtitle}</span>
              <span className="text-muted-foreground font-mono">Sotlas Unified Spec v0.4</span>
            </div>
          </div>

          {/* Right Column: Live Execution Simulator (5 cols) */}
          <div className="lg:col-span-5 flex flex-col rounded-2xl border border-border bg-card dark:bg-[#0C0D0E] overflow-hidden shadow-sm">
            {/* Simulator Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-muted/60 dark:bg-[#151619] border-b border-border">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2.5 w-2.5">
                  {isPlaying && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  )}
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
                </span>
                <span className="font-mono text-xs font-semibold text-foreground">
                  Execution Simulator
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  title={isPlaying ? "Pause" : "Play"}
                  className="p-1.5 rounded-lg bg-muted hover:bg-accent text-foreground transition-colors"
                >
                  {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                </button>
                <button
                  onClick={() => {
                    setCurrentStepIndex(0);
                    setLoopCount(1);
                  }}
                  title="Reset cycle"
                  className="p-1.5 rounded-lg bg-muted hover:bg-accent text-foreground transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Real-time Telemetry Metrics */}
            <div className="p-3 grid grid-cols-2 gap-2 border-b border-border bg-muted/30 dark:bg-[#101114]">
              {scenario.metrics.map((metric, idx) => (
                <div key={idx} className="p-2 rounded-xl bg-card border border-border flex flex-col shadow-2xs">
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{metric.label}</span>
                  <div className="flex items-baseline justify-between mt-1">
                    <span className="font-mono text-xs font-semibold text-foreground">{metric.value}</span>
                    {metric.badge && (
                      <span className="text-[9px] font-mono px-1 rounded bg-muted text-emerald-600 dark:text-emerald-400 border border-border">
                        {metric.badge}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Terminal Live Event Log Stream */}
            <div
              ref={terminalLogsRef}
              className="p-4 font-mono text-xs overflow-y-auto space-y-2 flex-1 max-h-[340px] scroll-smooth"
            >
              <AnimatePresence initial={false}>
                {visibleLogs.map((log, idx) => {
                  const isLatest = idx === currentStepIndex;
                  return (
                    <motion.div
                      key={`${loopCount}-${idx}`}
                      initial={{ opacity: 0, x: -6 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.2 }}
                      className={`flex items-start gap-2 p-1.5 rounded-lg transition-colors ${
                        isLatest ? "bg-zinc-900/90 border border-zinc-800" : ""
                      }`}
                    >
                      <span className="text-[10px] text-zinc-500 select-none pt-0.5">
                        +{log.timeMs}µs
                      </span>
                      {log.type === "hw" && (
                        <span className="text-[9px] px-1 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 font-semibold select-none">
                          HW
                        </span>
                      )}
                      {log.type === "srg" && (
                        <span className="text-[9px] px-1 py-0.5 rounded bg-violet-950/80 text-violet-300 border border-violet-800/60 font-semibold select-none">
                          SRG
                        </span>
                      )}
                      {log.type === "cycle" && (
                        <span className="text-[9px] px-1 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-800/60 font-semibold select-none">
                          ATOM
                        </span>
                      )}
                      {log.type === "ok" && (
                        <span className="text-[9px] px-1 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 font-semibold select-none">
                          OK
                        </span>
                      )}
                      {log.type === "sys" && (
                        <span className="text-[9px] px-1 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700 font-semibold select-none">
                          SYS
                        </span>
                      )}
                      <span
                        className={`leading-relaxed text-[11px] ${
                          isLatest ? "text-foreground font-medium" : "text-zinc-400"
                        }`}
                      >
                        {log.message}
                      </span>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>

            {/* Terminal Status Bar */}
            <div className="px-4 py-2.5 bg-[#121316] border-t border-border/50 text-[11px] font-mono text-zinc-400 flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span>Status: Active & Fault-Free</span>
              </div>
              <span className="text-zinc-500">
                Step {currentStepIndex + 1}/{scenario.logs.length}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CodeShowcase;
