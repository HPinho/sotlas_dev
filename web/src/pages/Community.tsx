import { Bug, ExternalLink, Github, GitPullRequest } from "lucide-react";
import { Link } from "react-router-dom";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Seo } from "@/components/Seo";

const repository = "https://github.com/HPinho/sotlas_dev";
const links = [
  { icon: Github, title: "Source code", detail: "Read the compiler, tests, examples, and preview documentation.", href: repository },
  { icon: Bug, title: "Report a problem", detail: "Include the commit, operating system, backend, command, and a small reproducer.", href: `${repository}/issues` },
  { icon: GitPullRequest, title: "Propose a change", detail: "Submit test-backed fixes and keep public claims tied to verified behavior.", href: `${repository}/pulls` },
];

export default function Community() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Seo title="Contribute — Sotlas" description="Review the Sotlas development preview, report reproducible issues, and contribute test-backed changes." path="/community" />
      <Navbar />
      <main className="mx-auto w-full max-w-5xl flex-1 px-5 pb-16 pt-32 md:px-8">
        <p className="font-mono text-xs uppercase tracking-wider text-primary">Development community</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight md:text-4xl">Help improve the preview</h1>
        <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground">
          Sotlas is under active development. The repository is the source of truth for current behavior;
          its roadmap includes work that has not reached the preview contract yet.
        </p>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {links.map(({ icon: Icon, title, detail, href }) => (
            <a key={title} href={href} target="_blank" rel="noreferrer" className="rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/40">
              <Icon className="h-5 w-5 text-primary" />
              <h2 className="mt-4 font-semibold">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
              <span className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-primary">Open GitHub <ExternalLink className="h-3.5 w-3.5" /></span>
            </a>
          ))}
        </div>
        <div className="mt-8 rounded-xl border border-border p-5">
          <h2 className="font-semibold">Before opening an issue</h2>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm leading-6 text-muted-foreground">
            <li>Check the documented backend and feature subset.</li>
            <li>Run the smallest source file that reproduces the result.</li>
            <li>Do not include private source code, credentials, or personal data in a public issue.</li>
          </ul>
          <Link to="/docs/guarantees" className="mt-4 inline-block text-sm font-medium text-primary">Read the preview guarantees</Link>
        </div>
      </main>
      <Footer />
    </div>
  );
}
