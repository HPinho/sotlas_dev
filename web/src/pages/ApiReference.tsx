import { Link } from "react-router-dom";
import { ArrowRight, Github } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Seo } from "@/components/Seo";

export default function ApiReference() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Seo title="Registry API — Sotlas" description="The Sotlas preview does not currently provide a hosted package registry API." path="/api" />
      <Navbar />
      <main className="mx-auto w-full max-w-3xl flex-1 px-5 pb-16 pt-32 md:px-8">
        <p className="font-mono text-xs uppercase tracking-wider text-primary">API status</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight md:text-4xl">No hosted registry API is available</h1>
        <p className="mt-5 text-base leading-7 text-muted-foreground">
          Earlier versions of this page listed package search, publishing, and account endpoints. Those
          endpoints are not implemented by the current preview, so the examples have been removed.
          Package tooling in the repository is experimental and does not connect to a public registry.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/docs/overview" className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground">Read preview scope <ArrowRight className="h-4 w-4" /></Link>
          <a href="https://github.com/HPinho/sotlas_dev" target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2.5 text-sm font-semibold"><Github className="h-4 w-4" />Development repository</a>
        </div>
      </main>
      <Footer />
    </div>
  );
}
