import { motion } from "framer-motion";
import {
  Github,
  MessageSquare,
  Users,
  BookOpen,
  ArrowRight,
  GitPullRequest,
  Bug,
  Heart,
  Rocket,
  Shield,
  Zap,
  Globe,
  Star,
  CheckCircle2,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Seo } from "@/components/Seo";
import WaveText from "@/components/ui/wave-text";

const communityLinks = [
  {
    icon: Github,
    title: "GitHub Repository",
    description: "Browse source code, star the project, and track development progress.",
    href: "https://github.com/Sotlas/sotlas",
    external: true,
    tag: "Source Code",
    tagColor: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
  },
  {
    icon: MessageSquare,
    title: "GitHub Discussions",
    description: "Ask questions, share ideas, and discuss language design decisions with the community.",
    href: "https://github.com/Sotlas/sotlas/discussions",
    external: true,
    tag: "Q&A",
    tagColor: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  },
  {
    icon: Bug,
    title: "Report Issues",
    description: "Found a bug in the compiler or documentation? File an issue and help improve Sotlas.",
    href: "https://github.com/Sotlas/sotlas/issues",
    external: true,
    tag: "Bug Reports",
    tagColor: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  },
  {
    icon: GitPullRequest,
    title: "Contribute",
    description: "Submit pull requests for compiler improvements, test coverage, and documentation.",
    href: "https://github.com/Sotlas/sotlas/pulls",
    external: true,
    tag: "PRs Welcome",
    tagColor: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  },
];

const contributionAreas = [
  {
    icon: Zap,
    title: "Compiler (SIR SSA)",
    description: "Optimize passes, add new backends, and improve code generation quality.",
    link: "/docs/compiler",
  },
  {
    icon: Shield,
    title: "SRG Memory Analysis",
    description: "Enhance the Scoped Reference Graph analysis with new ownership patterns.",
    link: "/docs/memory",
  },
  {
    icon: BookOpen,
    title: "Documentation",
    description: "Write guides, translate content, improve API references and examples.",
    link: "/docs/overview",
  },
  {
    icon: Globe,
    title: "Standard Library",
    description: "Expand stdlib modules: collections, I/O, crypto, and networking primitives.",
    link: "/docs/stdlib",
  },
];

const roadmapItems = [
  {
    phase: "v0.5",
    status: "current" as const,
    title: "Foundation & Core Language",
    items: [
      "Full lexer, parser, and semantic analysis",
      "SRG memory graph with sole/handover",
      "C11 backend code generation",
      "Topology Pointers (*rawphys, *portwire, *dmazone)",
      "298+ unit tests with CI/CD",
    ],
  },
  {
    phase: "v0.6",
    status: "next" as const,
    title: "Advanced Features",
    items: [
      "Island-based concurrency model",
      "WebAssembly (WASM) target",
      "Package manager (sotlas pkg)",
      "LSP server for editor integration",
      "Expanded stdlib (networking, crypto)",
    ],
  },
  {
    phase: "v1.0",
    status: "future" as const,
    title: "Production Ready",
    items: [
      "Stable language specification",
      "Self-hosting compiler (bootstrap)",
      "Full LLVM backend",
      "RISC-V and ARM Cortex-M targets",
      "Formal verification integration",
    ],
  },
];

function CommunityCard({
  icon: Icon,
  title,
  description,
  href,
  external,
  tag,
  tagColor,
  index,
}: (typeof communityLinks)[0] & { index: number }) {
  const content = (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.1 }}
      transition={{ duration: 0.4, delay: index * 0.08 }}
      className="group rounded-2xl border border-border bg-card p-6 hover:border-primary/40 hover:shadow-xl transition-all duration-300 flex flex-col justify-between h-full"
    >
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="w-11 h-11 rounded-xl bg-muted/80 border border-border flex items-center justify-center group-hover:scale-105 transition-transform">
            <Icon className="w-5 h-5 text-foreground" />
          </div>
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded-md border ${tagColor}`}>
            {tag}
          </span>
        </div>
        <h3 className="text-base font-bold text-foreground mb-2 group-hover:text-primary transition-colors">
          {title}
        </h3>
        <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
      </div>
      <div className="mt-4 pt-3 border-t border-border/60 flex items-center gap-1.5 text-xs font-mono text-muted-foreground group-hover:text-primary transition-colors">
        <span>{external ? "Open on GitHub" : "Learn more"}</span>
        <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1" />
      </div>
    </motion.div>
  );

  if (external) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="block h-full">
        {content}
      </a>
    );
  }

  return (
    <Link to={href} className="block h-full">
      {content}
    </Link>
  );
}

export default function Community() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Seo
        title="Community — Sotlas"
        description="Join the Sotlas community: contribute to the compiler, report issues, discuss language design, and track the roadmap."
        path="/community"
      />
      <Navbar />

      <main className="flex-1 pt-20 pb-16">
        <div className="max-w-6xl mx-auto px-4 md:px-8">
          {/* Hero Header */}
          <motion.div
            className="text-center mb-14"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-mono mb-4">
              <Users className="w-3.5 h-3.5" />
              <span>Open Source Community</span>
            </div>
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground tracking-tight mb-4">
              <WaveText text="Build the future of systems programming" />
            </h1>
            <p className="text-muted-foreground text-base md:text-lg max-w-2xl mx-auto leading-relaxed">
              Sotlas is open source under Apache 2.0. Every contribution — from compiler patches to documentation fixes — helps shape a safer, more expressive systems language.
            </p>
          </motion.div>

          {/* Community Links Grid */}
          <section className="mb-20">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {communityLinks.map((link, idx) => (
                <CommunityCard key={link.title} {...link} index={idx} />
              ))}
            </div>
          </section>

          {/* Contribution Areas */}
          <section className="mb-20">
            <motion.div
              className="text-center mb-10"
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
            >
              <h2 className="text-2xl md:text-3xl font-bold text-foreground tracking-tight mb-3">
                <WaveText text="Where to contribute" />
              </h2>
              <p className="text-muted-foreground text-sm max-w-xl mx-auto">
                Whether you're a compiler engineer, technical writer, or systems enthusiast — there's a place for your expertise.
              </p>
            </motion.div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {contributionAreas.map((area, idx) => {
                const AreaIcon = area.icon;
                return (
                  <motion.div
                    key={area.title}
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.4, delay: idx * 0.08 }}
                  >
                    <Link
                      to={area.link}
                      className="block rounded-2xl border border-border bg-card p-5 hover:border-primary/40 transition-all group"
                    >
                      <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                        <AreaIcon className="w-5 h-5 text-primary" />
                      </div>
                      <h3 className="text-sm font-bold text-foreground mb-1 group-hover:text-primary transition-colors">
                        {area.title}
                      </h3>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        {area.description}
                      </p>
                    </Link>
                  </motion.div>
                );
              })}
            </div>
          </section>

          {/* Roadmap */}
          <section className="mb-16">
            <motion.div
              className="text-center mb-10"
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
            >
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-400 text-xs font-mono mb-3">
                <Rocket className="w-3.5 h-3.5" />
                <span>Development Roadmap</span>
              </div>
              <h2 className="text-2xl md:text-3xl font-bold text-foreground tracking-tight mb-3">
                <WaveText text="Where Sotlas is headed" />
              </h2>
              <p className="text-muted-foreground text-sm max-w-xl mx-auto">
                A transparent view of the language evolution, from current capabilities to the self-hosting milestone.
              </p>
            </motion.div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {roadmapItems.map((phase, idx) => (
                <motion.div
                  key={phase.phase}
                  initial={{ opacity: 0, y: 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.4, delay: idx * 0.1 }}
                  className={`rounded-2xl border p-6 ${
                    phase.status === "current"
                      ? "border-primary/50 bg-primary/5 shadow-lg ring-1 ring-primary/20"
                      : "border-border bg-card"
                  }`}
                >
                  <div className="flex items-center gap-3 mb-4">
                    <span
                      className={`text-xs font-mono font-bold px-2.5 py-1 rounded-lg border ${
                        phase.status === "current"
                          ? "bg-primary/15 text-primary border-primary/30"
                          : phase.status === "next"
                          ? "bg-violet-500/10 text-violet-400 border-violet-500/20"
                          : "bg-muted text-muted-foreground border-border"
                      }`}
                    >
                      {phase.phase}
                    </span>
                    {phase.status === "current" && (
                      <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        Active
                      </span>
                    )}
                  </div>
                  <h3 className="text-base font-bold text-foreground mb-3">{phase.title}</h3>
                  <ul className="space-y-2">
                    {phase.items.map((item) => (
                      <li key={item} className="flex items-start gap-2 text-xs text-muted-foreground">
                        <CheckCircle2
                          className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${
                            phase.status === "current" ? "text-emerald-500" : "text-muted-foreground/40"
                          }`}
                        />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </motion.div>
              ))}
            </div>
          </section>

          {/* CTA */}
          <motion.div
            className="text-center rounded-3xl bg-gradient-to-b from-card to-muted/30 border border-border p-8 md:p-12"
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <Heart className="w-8 h-8 text-rose-400 mx-auto mb-4" />
            <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-3">
              Every contribution matters
            </h2>
            <p className="text-muted-foreground text-sm max-w-lg mx-auto mb-6">
              Whether it's a typo fix, a test case, or a new compiler pass — you're helping build safer systems software.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <a
                href="https://github.com/Sotlas/sotlas"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-foreground text-background font-semibold text-sm hover:opacity-90 transition-opacity shadow-md"
              >
                <Star className="w-4 h-4" />
                Star on GitHub
              </a>
              <Link
                to="/docs/installation"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-secondary hover:bg-secondary/80 border border-border text-foreground text-sm font-medium transition-colors"
              >
                <Rocket className="w-4 h-4 text-primary" />
                Get Started
              </Link>
            </div>
          </motion.div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
