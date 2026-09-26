import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { ChangelogEntry } from "@/components/changelog";
import WaveText from "@/components/ui/wave-text";
import { changelogData } from "@/data/changelog";
import { Seo } from "@/components/Seo";

const Changelog = () => {
  return (
    <div className="min-h-screen bg-background">
      <Seo
        title="Changelog — Sotlas"
        description="Development notes for the Sotlas preview. These entries are not published release notes."
        path="/changelog"
      />
      <Navbar />
      
      <main className="pt-24 pb-16">
        <div className="max-w-4xl mx-auto px-4 md:px-8">
          {/* Header */}
          <div className="mb-16">
            <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-3 tracking-tight">
              <WaveText text="Changelog" />
            </h1>
            <p className="text-xl text-primary font-medium mb-4">
              <WaveText text="Development updates" staggerDelay={0.02} />
            </p>
            <p className="text-muted-foreground max-w-2xl">
              <WaveText text="This page summarizes the current development snapshot. It does not list published releases; check the repository history for the full change record." staggerDelay={0.01} />
            </p>
            <a className="mt-4 inline-block text-sm font-medium text-primary" href="https://github.com/HPinho/sotlas_dev/commits/main" target="_blank" rel="noreferrer">View development history on GitHub</a>
          </div>

          {/* Changelog Entries */}
          <div className="space-y-12">
            {changelogData.map((entry, index) => (
              <ChangelogEntry
                key={index}
                date={entry.date}
                badges={entry.badges}
                sections={entry.sections}
                index={index}
              />
            ))}
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default Changelog;
