import { useState } from "react";
import { Check, Copy, ExternalLink, FileCode2, Terminal } from "lucide-react";
import { Link } from "react-router-dom";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Seo } from "@/components/Seo";
import helloSource from "../../../examples/01_hello_systems/main.sotlas?raw";
import dispatchSource from "../../../examples/07_cli_tool/main.sotlas?raw";

const examples = [
  {
    id: "hello",
    name: "Hello Systems",
    path: "examples/01_hello_systems/main.sotlas",
    source: "https://github.com/HPinho/sotlas_dev/blob/main/examples/01_hello_systems/main.sotlas",
    code: helloSource.trimEnd(),
  },
  {
    id: "dispatch",
    name: "Enum Dispatch",
    path: "examples/07_cli_tool/main.sotlas",
    source: "https://github.com/HPinho/sotlas_dev/blob/main/examples/07_cli_tool/main.sotlas",
    code: dispatchSource.trimEnd(),
  },
];

export default function Playground() {
  const [selectedId, setSelectedId] = useState(examples[0].id);
  const [copied, setCopied] = useState(false);
  const selected = examples.find((example) => example.id === selectedId) || examples[0];

  const copySource = async () => {
    try {
      await navigator.clipboard.writeText(selected.code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Seo title="Examples — Sotlas" description="Browse checked source examples from the Sotlas development repository and run them locally." path="/playground" />
      <Navbar />
      <main className="mx-auto w-full max-w-6xl flex-1 px-5 pb-16 pt-28 md:px-8">
        <p className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 font-mono text-xs text-primary">
          <Terminal className="h-3.5 w-3.5" /> Source examples
        </p>
        <h1 className="mt-5 text-3xl font-semibold tracking-tight md:text-4xl">Examples you can run locally</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
          This page does not compile code in the browser. The source shown here is loaded directly from
          repository examples; CI checks both files and runs them through the C11 path.
        </p>

        <div className="mt-7 flex flex-wrap gap-2" role="tablist" aria-label="Sotlas examples">
          {examples.map((example) => (
            <button
              key={example.id}
              type="button"
              role="tab"
              aria-selected={selected.id === example.id}
              onClick={() => setSelectedId(example.id)}
              className={`rounded-lg border px-4 py-2 text-sm font-medium ${selected.id === example.id ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card hover:bg-muted"}`}
            >
              {example.name}
            </button>
          ))}
        </div>

        <section className="mt-4 overflow-hidden rounded-xl border border-border bg-card" aria-label={selected.name}>
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
            <span className="inline-flex items-center gap-2 font-mono text-xs text-muted-foreground"><FileCode2 className="h-4 w-4" />{selected.path}</span>
            <button type="button" onClick={copySource} className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted" aria-label="Copy source">
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}{copied ? "Copied" : "Copy source"}
            </button>
          </header>
          <pre className="max-h-[34rem] overflow-auto bg-zinc-950 p-5 text-xs leading-6 text-zinc-100"><code>{selected.code}</code></pre>
        </section>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <section className="rounded-xl border border-border p-5">
            <h2 className="font-semibold">Check and run</h2>
            <pre className="mt-3 overflow-x-auto rounded-lg bg-muted p-3 text-xs leading-6"><code>{`sotlas check ${selected.path}\nsotlas run ${selected.path}`}</code></pre>
            <p className="mt-3 text-xs leading-5 text-muted-foreground">Install the compiler from the repository first. Native execution needs GCC or Clang.</p>
          </section>
          <section className="rounded-xl border border-border p-5">
            <h2 className="font-semibold">Source and support status</h2>
            <a href={selected.source} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-2 text-sm text-primary">Open source file <ExternalLink className="h-4 w-4" /></a>
            <p className="mt-3 text-xs leading-5 text-muted-foreground">The examples are marked experimental in the manifest. Their CI execution demonstrates these exact programs, not general support for every related language feature.</p>
            <Link to="/docs/guarantees" className="mt-3 inline-block text-sm text-primary">Read the preview contract</Link>
          </section>
        </div>
      </main>
      <Footer />
    </div>
  );
}
