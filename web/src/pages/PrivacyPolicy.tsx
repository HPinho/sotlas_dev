import { ExternalLink, ShieldCheck } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Seo } from "@/components/Seo";

const browserState = [
  { name: "Theme", storage: "Browser local storage (`theme`)", purpose: "Remembers the selected display theme." },
  { name: "Documentation feedback", storage: "Browser local storage (`sotlas_feedback_<page>`)", purpose: "Remembers whether you marked a documentation page helpful." },
  { name: "Documentation sidebar", storage: "A `sidebar:state` browser cookie", purpose: "Remembers whether the sidebar is open." },
];

export function PrivacyPolicy() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Seo title="Website Privacy Notes — Sotlas" description="What the current Sotlas preview website stores in your browser and how its locally run compiler handles source code." path="/privacy" />
      <Navbar />
      <main className="mx-auto w-full max-w-4xl flex-1 px-5 pb-16 pt-32 md:px-8">
        <p className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 font-mono text-xs text-primary"><ShieldCheck className="h-3.5 w-3.5" /> Website privacy</p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight md:text-4xl">Privacy notes for the Sotlas preview site</h1>
        <p className="mt-4 text-sm leading-6 text-muted-foreground">
          This notice describes behavior visible in the current website source. The site owner has not
          supplied a legal entity, hosting-provider details, or a dedicated privacy contact, so this page
          does not invent those details or claim legal certification.
        </p>

        <section id="browser-storage" className="mt-10 border-t border-border pt-7">
          <h2 className="text-xl font-semibold">Browser storage</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">The current site stores the following preferences in your browser. The site code does not send these values to a Sotlas service.</p>
          <div className="mt-4 overflow-x-auto rounded-xl border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground"><tr><th className="p-3">Item</th><th className="p-3">Storage</th><th className="p-3">Purpose</th></tr></thead>
              <tbody>{browserState.map((item) => <tr key={item.name} className="border-t border-border"><td className="p-3 font-medium">{item.name}</td><td className="p-3 font-mono text-xs">{item.storage}</td><td className="p-3 text-muted-foreground">{item.purpose}</td></tr>)}</tbody>
            </table>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">You can clear this data using your browser's site-data controls. The page does not use an analytics SDK, advertising pixel, or compiler-telemetry client.</p>
        </section>

        <section className="mt-9 border-t border-border pt-7">
          <h2 className="text-xl font-semibold">Compiler and source files</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">The compiler in this preview runs on your own machine. The commands documented here do not upload source files to the Sotlas website. If you file a public issue, anything you include there may be visible to others; remove credentials and private code first.</p>
        </section>

        <section className="mt-9 border-t border-border pt-7">
          <h2 className="text-xl font-semibold">Hosting and external links</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">The website is served by a hosting provider. The provider may process request data such as IP address, browser headers, and requested URL to deliver and protect the site. The project has not published provider-specific retention details here. Links to GitHub and other sites are governed by those services' own privacy notices.</p>
        </section>

        <section className="mt-9 border-t border-border pt-7">
          <h2 className="text-xl font-semibold">Questions or corrections</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">For a privacy question, contact the project maintainer through the public profile below. Do not post personal information in a public issue.</p>
          <a className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-primary" href="https://github.com/HPinho" target="_blank" rel="noreferrer">Project maintainer on GitHub <ExternalLink className="h-4 w-4" /></a>
        </section>
      </main>
      <Footer />
    </div>
  );
}

export default PrivacyPolicy;
