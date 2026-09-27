import { ArrowRight, BookOpen, Check, Code2, Github, ShieldCheck, Terminal } from "lucide-react";
import { Link } from "react-router-dom";

const repository = "https://github.com/HPinho/sotlas_dev";

const evidence = [
  {
    icon: ShieldCheck,
    title: "A checked source path",
    text: "The installed CLI uses the canonical frontend for source checks and compilation.",
    detail: "sotlas check",
  },
  {
    icon: Code2,
    title: "Two documented backends",
    text: "C11 and LLVM have separate, bounded lowering contracts. Unsupported forms are rejected.",
    detail: "C11 + checked LLVM subset",
  },
  {
    icon: Terminal,
    title: "Examples in CI",
    text: "The preview workflow checks source examples and compiles the declared C11 contract examples.",
    detail: "See examples/manifest.json",
  },
];

const commands = [
  "git clone https://github.com/HPinho/sotlas_dev.git",
  "cd sotlas_dev",
  "python -m venv .venv",
  "# PowerShell: .\\.venv\\Scripts\\Activate.ps1",
  "# Linux/macOS: source .venv/bin/activate",
  "python -m pip install -e .",
  "sotlas check examples/01_hello_systems/main.sotlas",
  "sotlas run examples/01_hello_systems/main.sotlas",
];

export function SotlasLanding() {
  return (
    <div className="bg-background text-foreground">
      <section className="border-b border-border px-5 pb-20 pt-32 md:px-8 md:pb-28 md:pt-40">
        <div className="mx-auto max-w-5xl">
          <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 font-mono text-xs text-primary">
            Sotlas 1.0 development preview
          </p>
          <h1 className="max-w-4xl text-4xl font-semibold tracking-tight md:text-6xl">
            A systems language with explicit ownership rules.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-muted-foreground">
            Sotlas is an experimental compiled language. This preview lets you try its canonical
            source checks, bounded ownership model, and native compiler paths. Read the support
            limits before using it in a project.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/docs/installation" className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground">
              Try the preview <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/docs/overview" className="inline-flex items-center gap-2 rounded-lg border border-border px-5 py-3 text-sm font-semibold hover:bg-muted">
              Read the support contract <BookOpen className="h-4 w-4" />
            </Link>
          </div>
          <p className="mt-5 text-xs text-muted-foreground">
            Development package from GitHub · Python 3.10+ · GCC or Clang for native C11 execution
          </p>
        </div>
      </section>

      <section className="px-5 py-16 md:px-8 md:py-20">
        <div className="mx-auto max-w-5xl">
          <div className="mb-8 max-w-2xl">
            <p className="font-mono text-xs uppercase tracking-wider text-primary">What you can verify</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">Start with evidence from the repository</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {evidence.map(({ icon: Icon, title, text, detail }) => (
              <article key={title} className="rounded-xl border border-border bg-card p-5">
                <Icon className="h-5 w-5 text-primary" />
                <h3 className="mt-4 font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{text}</p>
                <code className="mt-4 block text-xs text-primary">{detail}</code>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y border-border bg-muted/30 px-5 py-16 md:px-8 md:py-20">
        <div className="mx-auto grid max-w-5xl gap-10 md:grid-cols-[1fr_1.1fr] md:items-center">
          <div>
            <p className="font-mono text-xs uppercase tracking-wider text-primary">Quick start</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">Run a checked example</h2>
            <p className="mt-4 text-sm leading-6 text-muted-foreground">
              The compiler is currently installed from source. The steps below use the development
              repository and do not require an unpublished installer.
            </p>
          </div>
          <pre className="overflow-x-auto rounded-xl border border-border bg-background p-5 text-xs leading-7"><code>{commands.map((command) => `$ ${command}`).join("\n")}</code></pre>
        </div>
      </section>

      <section className="px-5 py-16 md:px-8 md:py-20">
        <div className="mx-auto max-w-5xl">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
            <div>
              <p className="font-mono text-xs uppercase tracking-wider text-primary">Preview boundaries</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">Know what is covered</h2>
            </div>
            <Link to="/docs/guarantees" className="inline-flex items-center gap-2 text-sm font-medium text-primary">
              Read guarantees and limits <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="mt-7 grid gap-3 sm:grid-cols-2">
            {[
              "Ownership domains are supported only in documented subsets.",
              "C11 and LLVM do not have full feature parity.",
              "Hardware examples do not establish validated board support.",
              "Standard-library modules have different levels of runtime testing.",
            ].map((item) => <p key={item} className="flex gap-3 rounded-lg border border-border p-4 text-sm leading-6 text-muted-foreground"><Check className="mt-1 h-4 w-4 shrink-0 text-primary" />{item}</p>)}
          </div>
        </div>
      </section>

      <section className="border-t border-border px-5 py-12 md:px-8">
        <div className="mx-auto flex max-w-5xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-semibold">Help improve the preview</h2>
            <p className="mt-1 text-sm text-muted-foreground">Report a reproducible compiler issue or review the code and roadmap.</p>
          </div>
          <a href={repository} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-sm font-medium text-primary">
            <Github className="h-4 w-4" /> Development repository <ArrowRight className="h-4 w-4" />
          </a>
        </div>
      </section>
    </div>
  );
}

export default SotlasLanding;
