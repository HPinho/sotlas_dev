import { useRef } from "react";
import { Link } from "react-router-dom";
import { motion, useScroll, useTransform, useSpring } from "framer-motion";
import {
  ArrowRight,
  Binary,
  Boxes,
  Braces,
  Check,
  Cpu,
  Github,
  Layers3,
  ShieldCheck,
  TerminalSquare,
  Zap,
  Workflow,
  Radio,
  FileCode2,
} from "lucide-react";
import SotlasFlowBackground from "./SotlasFlowBackground";
import { InteropDiagram } from "@/components/interop-diagram";
import { Support } from "@/components/support";
import { CalloutBanner } from "@/components/callout";

interface CodeStory {
  id: string;
  icon: typeof ShieldCheck;
  label: string;
  title: string;
  text: string;
  highlights: string[];
  code: string[][];
  accent: "orange" | "blue" | "violet" | "emerald";
  docLink: string;
}


const pillars = [
  {
    icon: ShieldCheck,
    title: "Deterministic Memory Without GC",
    text: "The compiler statically validates ownership (sole) and atomic transfer (handover) with zero runtime GC pauses and no lifetime annotations.",
    link: "/docs/memory",
    accentColor: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
  {
    icon: Binary,
    title: "Hardware in the Type System",
    text: "Physical pointers (*rawphys), native bit-slicing (.slit[lo..hi]), and bus registers are verified types with static bounds.",
    link: "/docs/pointers",
    accentColor: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
  {
    icon: Zap,
    title: "Orthogonal Effects (@system)",
    text: "A formal boundary between pure logic and direct hardware mutations. Mutating buses requires explicit contract capabilities.",
    link: "/docs/keywords",
    accentColor: "text-purple-400 bg-purple-500/10 border-purple-500/20",
  },
  {
    icon: Workflow,
    title: "Zero-Cost SIR SSA & C11 Backend",
    text: "Sotlas Intermediate Representation (SIR) preserves silicon topology for strict SSA optimizations, generating C11 or native machine code.",
    link: "/docs/compiler",
    accentColor: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
];

const uses = [
  {
    icon: Cpu,
    title: "Firmware & Embedded",
    text: "Peripheral drivers, interrupt dispatching, and SPI/I2C/UART buses with zero hidden allocations.",
    href: "/docs/profiles",
    tag: "Bare-Metal",
  },
  {
    icon: Layers3,
    title: "Kernels & Hypervisors",
    text: "Page tables, DMA regions, and cooperative scheduling with isolated, verifiable memory.",
    href: "/docs/memory",
    tag: "Ring 0",
  },
  {
    icon: TerminalSquare,
    title: "Tools & Infrastructure",
    text: "High-throughput CLIs, strict parsers, and daemons with instant startup and minimal footprint.",
    href: "/docs/overview",
    tag: "Native Binaries",
  },
  {
    icon: Radio,
    title: "Real-Time Systems (RTOS)",
    text: "Audio processing, graphics engines, and industrial telemetry with hard determinism and zero pauses.",
    href: "/docs/hardware",
    tag: "Hard Realtime",
  },
];

const stories: CodeStory[] = [
  {
    id: "memory",
    icon: ShieldCheck,
    label: "Deterministic Lifecycle",
    title: "Memory with a clear path, zero GC.",
    text: "The Scoped Reference Graph (SRG) verifies resource ownership, atomic transfers, and scope isolation at compile time. Memory is freed at the exact deterministic moment, with zero GC pauses.",
    highlights: [
      "Exclusive ownership with sole prevents data races",
      "Atomic transfer via handover invalidates the source scope",
      "Static quarantine and deterministic zero-cost destruction",
    ],
    code: [
      ["// 1. Exclusive ownership mapping", ""],
      ["sole", " frame = FrameBuffer.map(0xA000_0000);"],
      ["", ""],
      ["// 2. Atomic transfer to compositor", ""],
      ["handover", " frame to compositor;"],
      ["", ""],
      ["// 3. Compiler statically rejects post-transfer use:", ""],
      ["// ERROR", ": `frame` has already been transferred"],
      ["// frame.render(); -> Rejected during SRG analysis", ""],
    ],
    accent: "orange",
    docLink: "/docs/memory",
  },
  {
    id: "hardware",
    icon: Binary,
    label: "Silicon Physics",
    title: "The type system understands the bus.",
    text: "Physical addresses, DMA regions, and MMIO registers are not untyped integers. The compiler statically validates bus bounds and hardware bit-slicing right in the language syntax.",
    highlights: [
      "Physical pointer *rawphys with verified hardware bus address",
      "Native bit-slicing .slit[lo..hi] without manual masks or shifts",
      "Direct bit access via .notch[n] with static validation",
    ],
    code: [
      ["// Physical register with static bus bounds", ""],
      ["let", " uart: *rawphys UInt32 = 0x1000_0000;"],
      ["", ""],
      ["// Native bit-slicing (TX FIFO Ready bit)", ""],
      ["let", " ready: Bool = uart.slit[5..5];"],
      ["", ""],
      ["if", " ready {"],
      ["  // Write byte to lower notch without manual bit-shifts", ""],
      ["  uart", ".notch[0..7] = tx_byte;"],
      ["}"],
    ],
    accent: "blue",
    docLink: "/docs/pointers",
  },
  {
    id: "atomic",
    icon: Zap,
    label: "Hardware Concurrency",
    title: "High-level syntax. Direct machine execution.",
    text: "Critical sections and interrupt dispatching use structured atomic blocks with guaranteed rollback handling if interrupted or aborted.",
    highlights: [
      "clinch ensures atomic CPU-level mutual exclusion",
      "revert restores state if interrupted or aborted",
      "Compiles to direct atomic sequences on target hardware",
    ],
    code: [
      ["@system", " fn configure_timer() {"],
      ["  // Atomic hardware block with safe rollback", ""],
      ["  clinch", " {"],
      ["    timer_regs", ".control.notch[2] = true;"],
      ["    timer_regs", ".period = 1000;"],
      ["  }", " revert {"],
      ["    // Executed if aborted or hardware interrupts", ""],
      ["    rebound;", ""],
      ["  }"],
      ["}"],
    ],
    accent: "violet",
    docLink: "/docs/hardware",
  },
  {
    id: "c-interop",
    icon: FileCode2,
    label: "Native C ABI",
    title: "Zero-overhead interoperability with C.",
    text: "No runtime bloat, no manual wrappers, and no foreign-function bridge penalty. Call standard POSIX, crypto, or vendor hardware libraries with zero call overhead.",
    highlights: [
      "Direct extern 'C' binding without fragile .h header dependencies",
      "Memory layout 100% identical to standard C ABI",
      "Self-contained binaries linkable with gcc, clang, or lld",
    ],
    code: [
      ["// Direct binding to standard C ABI symbols", ""],
      ["extern", ' "C" fn write(fd: Int32, buf: *rawphys UInt8, len: UInt) -> Int64;'],
      ["", ""],
      ["@system", " fn send_log(msg: String) {"],
      ["  let", " bytes = msg.as_bytes();"],
      ["  write", "(1, bytes.ptr, bytes.len);"],
      ["}"],
    ],
    accent: "emerald",
    docLink: "/docs/interoperability",
  },
];

const comparisonMatrix = [
  {
    feature: "Deterministic Memory Management",
    sotlas: "SRG (compile-time, zero pauses)",
    cLang: "Manual (malloc/free, risk of leaks)",
    rust: "Lifetimes and strict borrow checker",
    managedLang: "Garbage Collector or ARC with pauses",
  },
  {
    feature: "Physical Silicon Mapping (MMIO)",
    sotlas: "Native *rawphys + bit-slicing (.slit)",
    cLang: "Generic pointers and unsafe casts",
    rust: "Raw pointers inside unsafe blocks",
    managedLang: "Infeasible / abstracted by OS",
  },
  {
    feature: "Hardware Effect Boundary",
    sotlas: "Strict @system tracked by compiler",
    cLang: "None (any function touches I/O)",
    rust: "Generic unsafe without effect granularity",
    managedLang: "Non-existent in type system",
  },
  {
    feature: "Runtime Overhead",
    sotlas: "0 Bytes (pure freestanding)",
    cLang: "0 Bytes (freestanding)",
    rust: "Minimal (freestanding libcore)",
    managedLang: "High (GC/metadata runtime)",
  },
  {
    feature: "C ABI Interoperability",
    sotlas: "Native zero-cost (identical C layout)",
    cLang: "Native",
    rust: "extern 'C' with wrappers",
    managedLang: "Cgo / JNI with stack-switching penalty",
  },
];

function CodePanel({ lines, accent }: { lines: string[][]; accent: string }) {
  return (
    <div className={`sotlas-code sotlas-code--${accent}`}>
      <div className="sotlas-code__bar">
        <span />
        <span />
        <span />
        <small>kernel_sample.sot</small>
      </div>
      <pre>
        {lines.map(([keyword, rest], index) => (
          <code key={`${keyword}-${index}`}>
            <span>{keyword}</span>
            {rest}
          </code>
        ))}
      </pre>
    </div>
  );
}

export function SotlasLanding() {
  const heroRef = useRef<HTMLElement>(null);

  // Scroll parallax scoped to the Hero section only
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  });

  // Sunrise parallax (icon rises as you scroll)
  const sunriseParallaxY = useTransform(scrollYProgress, [0, 1], [0, -140]);
  const smoothSunriseY = useSpring(sunriseParallaxY, { stiffness: 100, damping: 20 });

  // Hero content: fade-out + drift upward on scroll
  const heroContentOpacity = useTransform(scrollYProgress, [0, 0.45], [1, 0]);
  const heroContentDriftY = useTransform(scrollYProgress, [0, 0.5], [0, -60]);

  // Sunrise glow: intensifies as scroll progresses
  const sunriseGlowOpacity = useTransform(scrollYProgress, [0, 0.7], [0.6, 1]);
  const sunriseGlowScale = useTransform(scrollYProgress, [0, 0.8], [1, 1.6]);

  // Stagger timing for entrance animations
  const staggerEase: [number, number, number, number] = [0.16, 1, 0.3, 1];

  return (
    <>
      {/* Scroll-reactive ribbon ribbons spanning the entire page */}
      <SotlasFlowBackground />

      {/* 1. HERO SECTION */}
      <section ref={heroRef} className="sotlas-hero">
        {/* Scroll-driven fade-out wrapper for all hero content */}
        <motion.div
          className="relative z-10 mx-auto flex min-h-[780px] max-w-7xl flex-col items-center justify-center px-4 pb-20 pt-24 text-center md:px-8"
          style={{ opacity: heroContentOpacity, y: heroContentDriftY }}
        >

          <motion.h1
            initial={{ opacity: 0, y: 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.1, ease: staggerEase }}
          >
            From silicon to application,<br />
            <em>control without compromise.</em>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.25, ease: staggerEase }}
          >
            Sotlas merges bare-metal machine predictability, deterministic Scoped Reference Graph (SRG) memory safety
            without a garbage collector, and modern expressiveness.
          </motion.p>

          <motion.div
            className="sotlas-hero__actions"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.4, ease: staggerEase }}
          >
            <Link to="/docs/installation" className="sotlas-button sotlas-button--primary">
              Install Sotlas <ArrowRight className="h-5 w-5" />
            </Link>
            <Link to="/docs/overview" className="sotlas-button sotlas-button--ghost">
              Explore Documentation
            </Link>
          </motion.div>

          <motion.div
            className="sotlas-hero__meta"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.55, ease: staggerEase }}
          >
            <span>Linux x86_64 / ARM64</span>
            <span>Windows x64</span>
            <span>macOS Apple Silicon</span>
            <span>RISC-V Embedded</span>
            <span>v0.5.1 Preview</span>
          </motion.div>
        </motion.div>

        {/* Sunrise Horizon Effect — emerges on load, parallax on scroll (hero only) */}
        <motion.div
          className="sotlas-hero__sunrise"
          aria-hidden="true"
          initial={{ y: 80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 1.4, ease: staggerEase, delay: 0.2 }}
        >
          <motion.div className="relative w-full h-full" style={{ y: smoothSunriseY }}>
            {/* Warm ambient glow — intensifies on scroll */}
            <motion.div
              className="sotlas-hero__sunrise-glow"
              style={{ opacity: sunriseGlowOpacity, scale: sunriseGlowScale }}
            />
            {/* The 3D torus icon, rising from the horizon */}
            <img
              src="/icone-sotlas.svg"
              alt=""
              className="sotlas-hero__sunrise-icon"
              draggable={false}
            />
          </motion.div>
        </motion.div>
      </section>

      {/* 2. PILLARS OF EXCELLENCE (WHY SOTLAS) */}
      <section className="relative border-t border-white/10 bg-[#05070d] px-4 py-20 md:px-8 md:py-28">
        <div className="mx-auto max-w-7xl">
          <div className="sotlas-section-heading">
            <span>Why Sotlas</span>
            <h2>Engineered to eliminate the critical gaps of safety and hardware.</h2>
          </div>

          <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {pillars.map(({ icon: Icon, title, text, link, accentColor }) => (
              <div
                key={title}
                className="group flex flex-col justify-between rounded-2xl border border-white/10 bg-slate-900/40 p-6 backdrop-blur-sm transition-all duration-200 hover:-translate-y-1 hover:border-orange-500/40 hover:bg-slate-900/70"
              >
                <div>
                  <div className={`flex h-11 w-11 items-center justify-center rounded-xl border ${accentColor}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-5 text-lg font-bold text-white group-hover:text-orange-400 transition-colors">
                    {title}
                  </h3>
                  <p className="mt-2.5 text-sm leading-relaxed text-slate-400">
                    {text}
                  </p>
                </div>
                <Link
                  to={link}
                  className="mt-6 inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-300 transition-colors group-hover:text-orange-400"
                >
                  Learn more <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 3. HARDWARE CAPABILITIES & CRITICAL LAYERS */}
      <section className="sotlas-uses">
        <div className="mx-auto max-w-7xl px-4 py-20 md:px-8 md:py-28">
          <div className="sotlas-section-heading">
            <span>Critical Layers</span>
            <h2>A systems language tailored for software that cannot fail.</h2>
          </div>

          <div className="sotlas-use-grid">
            {uses.map(({ icon: Icon, title, text, href, tag }) => (
              <Link key={title} to={href} className="sotlas-use-card group">
                <Icon className="h-7 w-7 text-sky-400 transition-transform group-hover:scale-110" />
                <div>
                  <div className="mb-1 inline-block rounded border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-mono text-slate-400">
                    {tag}
                  </div>
                  <h3 className="group-hover:text-orange-400 transition-colors">{title}</h3>
                  <p>{text}</p>
                </div>
                <ArrowRight className="h-5 w-5 text-slate-600 transition-transform group-hover:translate-x-1 group-hover:text-orange-400" />
              </Link>
            ))}
          </div>

          <div className="sotlas-use-links">
            <Link to="/docs/interoperability">
              <Braces className="h-4 w-4 text-orange-400" /> C & C++ Interoperability
            </Link>
            <Link to="/docs/keywords">
              <Boxes className="h-4 w-4 text-sky-400" /> Primitives & Effects
            </Link>
            <Link to="/docs/compiler">
              <Workflow className="h-4 w-4 text-purple-400" /> SIR Compilation Pipeline
            </Link>
          </div>
        </div>
      </section>

      {/* 4. CODE SHOWCASE & CORE STORIES */}
      <section className="sotlas-stories">
        <div className="mx-auto max-w-7xl px-4 pt-16 pb-4">
          <div className="sotlas-section-heading">
            <span>Code & Semantics</span>
            <h2>Experience Sotlas solving real-world systems challenges.</h2>
          </div>
        </div>

        {stories.map(({ icon: Icon, label, title, text, highlights, code, accent, docLink }, index) => (
          <article
            key={title}
            className={`sotlas-story ${index % 2 ? "sotlas-story--reverse" : ""}`}
          >
            <div className="sotlas-story__copy">
              <div className={`sotlas-story__icon sotlas-story__icon--${accent}`}>
                <Icon className="h-6 w-6" />
              </div>
              <span>{label}</span>
              <h2>{title}</h2>
              <p>{text}</p>

              <ul className="mt-4 space-y-2 text-sm text-slate-300">
                {highlights.map((h) => (
                  <li key={h} className="flex items-start gap-2">
                    <Check className="h-4 w-4 mt-0.5 text-emerald-400 shrink-0" />
                    <span>{h}</span>
                  </li>
                ))}
              </ul>

              <Link to={docLink}>
                Explore in documentation <ArrowRight className="h-4 w-4" />
              </Link>
            </div>

            <CodePanel lines={code} accent={accent} />
          </article>
        ))}
      </section>

      {/* 4c. INTEROPERABILITY DIAGRAM — 3 Layers */}
      <InteropDiagram />

      {/* 5. COMPARISON MATRIX (SOTLAS VS C/C++ VS RUST VS GO/MANAGED) */}
      <section className="relative border-t border-white/10 bg-[#070a13] px-4 py-20 md:px-8 md:py-28">
        <div className="mx-auto max-w-7xl">
          <div className="text-center max-w-3xl mx-auto mb-14">
            <span className="font-mono text-xs font-semibold uppercase tracking-[0.16em] text-orange-400">
              Comparative Analysis
            </span>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-white md:text-5xl">
              How Sotlas positions in the systems ecosystem
            </h2>
            <p className="mt-4 text-slate-400 text-base md:text-lg">
              A direct architectural comparison of systems programming languages for low-level development.
            </p>
          </div>

          <div className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-950/60 backdrop-blur-md shadow-2xl">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="border-b border-white/10 bg-white/[0.02] text-xs font-mono uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="p-4 md:p-6">Property</th>
                  <th className="p-4 md:p-6 text-orange-400 font-bold bg-orange-500/[0.05] border-x border-orange-500/20">
                    Sotlas
                  </th>
                  <th className="p-4 md:p-6">C / C++</th>
                  <th className="p-4 md:p-6">Rust</th>
                  <th className="p-4 md:p-6">Managed (Go / GC)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-sans">
                {comparisonMatrix.map((row) => (
                  <tr key={row.feature} className="hover:bg-white/[0.02] transition-colors">
                    <td className="p-4 md:p-6 font-semibold text-white">
                      {row.feature}
                    </td>
                    <td className="p-4 md:p-6 font-semibold text-orange-300 bg-orange-500/[0.03] border-x border-orange-500/10">
                      {row.sotlas}
                    </td>
                    <td className="p-4 md:p-6 text-slate-400">
                      {row.cLang}
                    </td>
                    <td className="p-4 md:p-6 text-slate-400">
                      {row.rust}
                    </td>
                    <td className="p-4 md:p-6 text-slate-400">
                      {row.managedLang}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* 6. MANIFESTO (IN DARK OBSIDIAN MODE) */}
      <section className="sotlas-manifesto">
        <div className="mx-auto max-w-5xl px-4 py-24 text-center md:px-8 md:py-36">
          <p>
            Low-level control should never force you to choose between{" "}
            <strong>performance</strong>, <strong>safety</strong>, and <strong>clarity</strong>.
          </p>
        </div>
      </section>

      {/* 6c. CALLOUT BANNER — CTA */}
      <CalloutBanner />

      {/* 6d. COMMUNITY & SUPPORT */}
      <Support />

      {/* 7. OPEN SOURCE CALLOUT */}
      <section className="sotlas-open-source">
        <div className="sotlas-open-source__mark">
          <img src="/icone-sotlas.svg" alt="Sotlas Logo" />
        </div>
        <div>
          <span>Open Source</span>
          <h2>A language evolving with those who build close to the metal.</h2>
          <p>
            Track engineering decisions, contribute to SIR compiler conformance tests, and help establish systems safety
            as a verifiable guarantee.
          </p>
        </div>
        <a
          href="https://github.com/Sotlas/sotlas"
          target="_blank"
          rel="noopener noreferrer"
          className="sotlas-button sotlas-button--light"
        >
          <Github className="h-5 w-5" /> View Repository on GitHub
        </a>
      </section>
    </>
  );
}

export default SotlasLanding;
