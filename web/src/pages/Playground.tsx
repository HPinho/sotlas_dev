import { useState } from "react";
import { motion } from "framer-motion";
import { Play, RotateCcw, Copy, Check, ChevronDown, Cpu, FileCode, Terminal } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Seo } from "@/components/Seo";

interface PlaygroundExample {
  id: string;
  name: string;
  description: string;
  category: string;
  code: string;
  output: string;
}

const examples: PlaygroundExample[] = [
  {
    id: "hello",
    name: "Hello Systems",
    description: "Your first Sotlas program: write to stdout via C ABI.",
    category: "Getting Started",
    code: `target native;
module hello;

extern "C" fn write(fd: Int32, buf: *rawphys UInt8, len: UInt) -> Int64;

pub fn main() -> Int32 {
    let msg = "Hello from Sotlas!\\n";
    let bytes = msg.as_bytes();
    write(1, bytes.ptr, bytes.len);
    return 0;
}`,
    output: `$ sotlas check hello.sot
✓ Lexer ......... 42 tokens
✓ Parser ........ AST validated
✓ Sema .......... types resolved, 0 errors
✓ SRG ........... ownership graph acyclic
✓ Codegen ....... C11 emitted (hello.c)

$ gcc hello.c -o hello && ./hello
Hello from Sotlas!`,
  },
  {
    id: "sole-ownership",
    name: "Sole Ownership",
    description: "Deterministic memory lifecycle with sole and handover.",
    category: "Memory Safety",
    code: `target native;
module memory_demo;

struct FrameBuffer {
    base: *rawphys UInt32;
    width: UInt32;
    height: UInt32;
}

impl FrameBuffer {
    pub fn map(addr: UInt64) -> sole FrameBuffer {
        return FrameBuffer {
            base: addr as *rawphys UInt32,
            width: 1920,
            height: 1080,
        };
    }

    pub fn render(self: &sole Self) {
        // Write pixels to framebuffer...
    }
}

pub fn main() -> Int32 {
    sole frame = FrameBuffer.map(0xA000_0000);
    frame.render();

    // Atomic transfer to compositor
    handover frame to compositor;

    // ERROR: \`frame\` has already been transferred
    // frame.render(); -> Rejected during SRG analysis
    return 0;
}`,
    output: `$ sotlas check memory_demo.sot
✓ Lexer ......... 87 tokens
✓ Parser ........ AST validated
✓ Sema .......... types resolved, 0 errors
✓ SRG ........... sole ownership verified
                  handover invalidates source scope
                  0 dangling references detected
✓ Codegen ....... C11 emitted

SRG Analysis Report:
  ├─ FrameBuffer: sole ownership (1 owner)
  ├─ handover: frame → compositor (atomic)
  └─ Post-transfer access: REJECTED ✗`,
  },
  {
    id: "hardware",
    name: "UART Hardware Driver",
    description: "Direct MMIO register access with bit-slicing.",
    category: "Bare-Metal",
    code: `target barecore;
module drivers::uart;

mesh UartRegisters {
    data:    UInt32 align(4);
    status:  UInt32 align(4);
    control: UInt32 align(4);
}

@system fn uart_init(base: UInt64) {
    let uart: *rawphys UartRegisters = base as *rawphys UartRegisters;

    clinch {
        // Configure: 8N1, 115200 baud
        uart.control.notch[0] = true;   // Enable TX
        uart.control.notch[1] = true;   // Enable RX
        uart.control.slit[4..7] = 0b11; // 8-bit word length
    } revert {
        rebound;
    }
}

@system fn uart_putchar(base: UInt64, ch: UInt8) {
    let uart: *rawphys UartRegisters = base as *rawphys UartRegisters;

    // Wait until TX FIFO is ready
    while !uart.status.notch[5] {}

    // Write character to data register
    uart.data.slit[0..7] = ch;
}`,
    output: `$ sotlas check uart.sot --target barecore
✓ Lexer ......... 108 tokens
✓ Parser ........ AST validated
✓ Sema .......... types resolved, 0 errors
✓ @system ....... hardware effects tracked
                  clinch block: atomic verified
                  *rawphys bus bounds: VALID
✓ SRG ........... no dynamic allocations
✓ Codegen ....... C11 freestanding emitted

Register Access Map:
  ├─ UartRegisters @ *rawphys (12 bytes)
  ├─ .notch[0], .notch[1]: single-bit access
  ├─ .slit[4..7]: 4-bit slice write
  └─ .slit[0..7]: 8-bit slice write`,
  },
  {
    id: "clinch",
    name: "Atomic Critical Section",
    description: "Hardware-level atomic blocks with structured rollback.",
    category: "Concurrency",
    code: `target barecore;
module kernel::timer;

mesh TimerRegs {
    control:  UInt32 align(4);
    period:   UInt32 align(4);
    counter:  UInt32 align(4);
    prescale: UInt32 align(4);
}

@system fn configure_timer(base: UInt64, hz: UInt32) {
    let regs: *rawphys TimerRegs = base as *rawphys TimerRegs;

    // Atomic hardware block with safe rollback
    clinch {
        regs.control.notch[0] = false; // Disable timer
        regs.prescale = 0;
        regs.period = 1_000_000 / hz;
        regs.control.notch[2] = true;  // Auto-reload
        regs.control.notch[0] = true;  // Re-enable
    } revert {
        // Executed if aborted or hardware fault
        regs.control.notch[0] = false;
        rebound;
    }
}

trapfn timer_irq_handler() {
    clinch {
        // Acknowledge interrupt
        outb(0x20, 0x20);
    }
    rebound;
}`,
    output: `$ sotlas check timer.sot --target barecore
✓ Lexer ......... 124 tokens
✓ Parser ........ AST validated
✓ Sema .......... types resolved, 0 errors
✓ @system ....... all hardware effects bounded
                  clinch: 2 atomic sections verified
                  trapfn: interrupt handler validated
✓ SRG ........... static allocation only
✓ Codegen ....... C11 freestanding emitted

Atomic Analysis:
  ├─ configure_timer: clinch + revert (paired)
  ├─ timer_irq_handler: trapfn (no-return)
  └─ All register writes: within @system boundary`,
  },
  {
    id: "interop",
    name: "C Interoperability",
    description: "Zero-overhead C ABI bindings — no wrappers needed.",
    category: "Interop",
    code: `target native;
module crypto_wrapper;

// Direct binding to OpenSSL — zero wrapper overhead
extern "C" fn SHA256(
    data: *rawphys UInt8,
    len: UInt,
    md: *rawphys UInt8
) -> *rawphys UInt8;

extern "C" fn strlen(s: *rawphys UInt8) -> UInt;

pub struct HashResult {
    bytes: [UInt8; 32];
}

@system pub fn hash_message(msg: String) -> HashResult {
    let raw = msg.as_bytes();
    var result = HashResult { bytes: [0; 32] };

    unsafe {
        SHA256(raw.ptr, raw.len, &result.bytes[0] as *rawphys UInt8);
    }

    return result;
}

pub fn main() -> Int32 {
    let digest = hash_message("Sotlas");
    // digest.bytes contains SHA-256 hash
    return 0;
}`,
    output: `$ sotlas check crypto.sot
✓ Lexer ......... 96 tokens
✓ Parser ........ AST validated
✓ Sema .......... types resolved, 0 errors
✓ @system ....... effect boundary: hash_message
                  unsafe block: FFI pointer access
✓ SRG ........... HashResult: value semantics (stack)
                  No heap allocations detected
✓ Codegen ....... C11 emitted (crypto.c)

Interop Report:
  ├─ extern "C" SHA256: linked via C ABI
  ├─ extern "C" strlen: linked via C ABI
  ├─ Memory layout: 100% C-compatible
  └─ Link: gcc crypto.c -lssl -lcrypto`,
  },
];

function SyntaxHighlighter({ code }: { code: string }) {
  const keywords = [
    "target", "module", "extern", "pub", "fn", "let", "var", "return",
    "struct", "impl", "mesh", "sole", "handover", "to", "clinch", "revert",
    "rebound", "trapfn", "unsafe", "while", "if", "as", "Self",
    "@system",
  ];
  const types = [
    "Int32", "Int64", "UInt8", "UInt32", "UInt64", "UInt", "Void",
    "Bool", "String", "bool",
  ];

  const lines = code.split("\n");

  return (
    <pre className="text-[13px] leading-relaxed font-mono">
      {lines.map((line, i) => {
        // Comment
        if (line.trim().startsWith("//")) {
          return <div key={i} className="text-slate-500 italic">{line}</div>;
        }

        // Tokenize
        let result = line;
        // First highlight strings
        const parts: React.ReactNode[] = [];
        let remaining = line;
        let keyIdx = 0;

        // Simple approach: split by tokens
        const tokens = remaining.split(/(\s+|[{}();,\[\]&*])/);
        tokens.forEach((token, tIdx) => {
          if (keywords.includes(token)) {
            parts.push(<span key={`${i}-${tIdx}`} className="text-orange-400 font-semibold">{token}</span>);
          } else if (types.includes(token)) {
            parts.push(<span key={`${i}-${tIdx}`} className="text-sky-400">{token}</span>);
          } else if (token.startsWith('"') || token.startsWith("'")) {
            parts.push(<span key={`${i}-${tIdx}`} className="text-emerald-400">{token}</span>);
          } else if (/^\d/.test(token) || token.startsWith("0x") || token.startsWith("0b")) {
            parts.push(<span key={`${i}-${tIdx}`} className="text-violet-400">{token}</span>);
          } else {
            parts.push(<span key={`${i}-${tIdx}`}>{token}</span>);
          }
        });

        return <div key={i}>{parts}</div>;
      })}
    </pre>
  );
}

export default function Playground() {
  const [selectedId, setSelectedId] = useState(examples[0].id);
  const [copied, setCopied] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);

  const selected = examples.find((e) => e.id === selectedId) || examples[0];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(selected.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* noop */ }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Seo
        title="Playground — Sotlas"
        description="Explore Sotlas code examples interactively: ownership, hardware drivers, atomics, and C interop."
        path="/playground"
      />
      <Navbar />

      <main className="flex-1 pt-20 pb-12">
        <div className="max-w-[90rem] mx-auto px-4 md:px-8">
          {/* Header */}
          <motion.div
            className="mb-8"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-mono mb-3">
              <Terminal className="w-3.5 h-3.5" />
              <span>Interactive Examples</span>
            </div>
            <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight mb-2">
              Sotlas Playground
            </h1>
            <p className="text-muted-foreground text-sm md:text-base max-w-2xl">
              Explore real Sotlas code examples with simulated compiler output. Select a scenario to see how the compiler analyzes, validates, and compiles it.
            </p>
          </motion.div>

          {/* Example Selector */}
          <div className="flex flex-wrap gap-2 mb-6">
            {examples.map((ex) => (
              <button
                key={ex.id}
                onClick={() => setSelectedId(ex.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  selectedId === ex.id
                    ? "bg-primary text-primary-foreground shadow-md"
                    : "bg-card border border-border text-muted-foreground hover:text-foreground hover:border-primary/40"
                }`}
              >
                {ex.name}
              </button>
            ))}
          </div>

          {/* Description Banner */}
          <motion.div
            key={selected.id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mb-4 p-3 rounded-xl bg-card border border-border flex items-center gap-3"
          >
            <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0">
              <Cpu className="w-4 h-4 text-primary" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">{selected.name}</p>
              <p className="text-xs text-muted-foreground">{selected.description}</p>
            </div>
            <span className="ml-auto text-[10px] font-mono px-2 py-0.5 rounded-md bg-muted border border-border text-muted-foreground shrink-0">
              {selected.category}
            </span>
          </motion.div>

          {/* Split Pane: Code + Output */}
          <motion.div
            key={`pane-${selected.id}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="grid grid-cols-1 lg:grid-cols-2 gap-4"
          >
            {/* Code Editor Panel */}
            <div className="rounded-2xl border border-border overflow-hidden shadow-xl">
              {/* Title Bar */}
              <div className="flex items-center justify-between px-4 py-2.5 bg-zinc-900 border-b border-zinc-800">
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-rose-500/80" />
                  <span className="w-3 h-3 rounded-full bg-amber-500/80" />
                  <span className="w-3 h-3 rounded-full bg-emerald-500/80" />
                </div>
                <span className="text-[11px] font-mono text-zinc-500">
                  <FileCode className="w-3 h-3 inline mr-1" />
                  {selected.id}.sot
                </span>
                <button
                  onClick={handleCopy}
                  className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-white/10 transition-colors"
                  title="Copy code"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>

              {/* Code Body */}
              <div className="bg-[#0a0a0f] p-5 overflow-x-auto min-h-[400px] max-h-[600px] overflow-y-auto">
                <SyntaxHighlighter code={selected.code} />
              </div>
            </div>

            {/* Output Panel */}
            <div className="rounded-2xl border border-border overflow-hidden shadow-xl">
              {/* Title Bar */}
              <div className="flex items-center justify-between px-4 py-2.5 bg-zinc-900 border-b border-zinc-800">
                <div className="flex items-center gap-2">
                  <Terminal className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-[11px] font-mono text-zinc-400">Compiler Output</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    Simulated
                  </span>
                </div>
              </div>

              {/* Output Body */}
              <div className="bg-[#0a0a0f] p-5 overflow-x-auto min-h-[400px] max-h-[600px] overflow-y-auto font-mono text-[12px] leading-relaxed">
                {selected.output.split("\n").map((line, i) => {
                  let className = "text-zinc-400";
                  if (line.startsWith("$")) className = "text-emerald-400 font-semibold";
                  else if (line.includes("✓")) className = "text-emerald-400";
                  else if (line.includes("✗") || line.includes("REJECTED")) className = "text-rose-400";
                  else if (line.includes("ERROR")) className = "text-rose-400 font-semibold";
                  else if (line.startsWith("  ├─") || line.startsWith("  └─")) className = "text-sky-400/80";
                  else if (line.includes("Report") || line.includes("Analysis") || line.includes("Map")) className = "text-amber-400 font-semibold mt-2";

                  return (
                    <div key={i} className={className}>
                      {line || "\u00A0"}
                    </div>
                  );
                })}
              </div>
            </div>
          </motion.div>

          {/* Disclaimer */}
          <p className="mt-6 text-center text-xs text-muted-foreground">
            Output is simulated for demonstration purposes. The Sotlas compiler is under active development.
          </p>
        </div>
      </main>

      <Footer />
    </div>
  );
}
