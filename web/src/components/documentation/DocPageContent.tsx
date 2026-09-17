import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
import { DocBreadcrumb } from "./DocBreadcrumb";
import { DocSection } from "./DocSection";
import { documentationPages, DocPageCode } from "@/data/documentation-pages";
import { navigationGroups } from "@/data/documentation";
import WaveText from "@/components/ui/wave-text";
import { CodeShowcase } from "@/components/code-showcase";

function CodeBlock({ code }: { code: DocPageCode }) {
  const [copied, setCopied] = useState(false);
  const text = code.lines.join("\n");

  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mt-4 rounded-xl bg-muted/40 dark:bg-muted/20 border border-border overflow-hidden shadow-2xs group relative">
      <div className="px-4 py-2 text-xs font-mono text-muted-foreground border-b border-border bg-muted/70 dark:bg-muted/40 flex items-center justify-between">
        <span>{code.caption || "Sotlas Code"}</span>
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground/80 font-semibold">
            Sotlas
          </span>
          <button
            type="button"
            onClick={handleCopy}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-background/80 transition-colors flex items-center gap-1 cursor-pointer"
            title="Copy code to clipboard"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-[10px] text-emerald-400">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span className="text-[10px]">Copy</span>
              </>
            )}
          </button>
        </div>
      </div>
      <div className="p-4 font-mono text-xs md:text-sm overflow-x-auto text-foreground/90 leading-relaxed whitespace-pre font-normal selection:bg-primary/20">
        {text}
      </div>
    </div>
  );
}

export function DocPageContent() {
  const params = useParams();
  const pageSlug = params["*"] || "overview";

  const page = documentationPages[pageSlug] || documentationPages["overview"];

  // Page feedback state
  const [feedbackGiven, setFeedbackGiven] = useState<"yes" | "no" | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(`sotlas_feedback_${pageSlug}`);
      if (stored === "yes" || stored === "no") {
        setFeedbackGiven(stored);
      } else {
        setFeedbackGiven(null);
      }
    } catch {
      setFeedbackGiven(null);
    }
  }, [pageSlug]);

  const handleFeedback = (type: "yes" | "no") => {
    setFeedbackGiven(type);
    try {
      localStorage.setItem(`sotlas_feedback_${pageSlug}`, type);
    } catch {
      // ignore
    }
  };

  // Compute Prev and Next pages
  const allItems = navigationGroups.flatMap((group) => group.items);
  const currentIndex = allItems.findIndex(
    (item) => item.href === `/docs/${pageSlug}` || item.id === pageSlug
  );
  const prevPage = currentIndex > 0 ? allItems[currentIndex - 1] : null;
  const nextPage =
    currentIndex >= 0 && currentIndex < allItems.length - 1
      ? allItems[currentIndex + 1]
      : null;

  if (!page) {
    return (
      <main className="flex-1 min-w-0 px-6 lg:px-12 pt-16 lg:pt-10 pb-10">
        <div className="max-w-3xl">
          <h1 className="text-4xl font-bold tracking-tight mb-4">Page Not Found</h1>
          <p className="text-lg text-muted-foreground">
            The documentation page you're looking for doesn't exist.
          </p>
        </div>
      </main>
    );
  }

  return (
    <motion.main
      key={pageSlug}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
      className="flex-1 min-w-0 px-4 md:px-6 lg:px-12 pt-16 lg:pt-10 pb-10 overflow-hidden"
    >
      <div className="max-w-3xl w-full">
        <DocBreadcrumb items={page.breadcrumb} />

        <div>
          <h1 className="text-4xl font-bold tracking-tight mb-4">
            <WaveText text={page.title} />
          </h1>
          <p className="text-lg text-muted-foreground mb-12">{page.description}</p>
        </div>

        <div className="space-y-12">
          {page.sections.map((section) => (
            <DocSection key={section.id} id={section.id} title={section.title} level={section.level}>
              <p>{section.content}</p>
              {section.listItems &&
                (section.orderedList ? (
                  <ol className="list-decimal list-inside space-y-2 ml-2 mt-4">
                    {section.listItems.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ol>
                ) : (
                  <ul className="list-disc list-inside space-y-2 ml-2 mt-4">
                    {section.listItems.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                ))}
              {section.code && <CodeBlock code={section.code} />}
            </DocSection>
          ))}
        </div>

        {pageSlug === "overview" && (
          <div className="mt-14 pt-8 border-t border-border/80">
            <div className="mb-4">
              <h3 className="text-xl font-bold tracking-tight text-foreground">
                Execution Simulator & Interactive Scenarios
              </h3>
              <p className="text-sm text-muted-foreground mt-1">
                Explore syntax in real-time with continuous execution telemetry and deterministic state tracking.
              </p>
            </div>
            <CodeShowcase embedded={true} />
          </div>
        )}

        {/* Helpful Feedback Widget */}
        <div className="mt-16 pt-8 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-4 p-5 rounded-2xl bg-card border shadow-xs">
          <div>
            <p className="text-sm font-semibold text-foreground">Was this page helpful?</p>
            <p className="text-xs text-muted-foreground">
              Your feedback directly guides the Sotlas language documentation team.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {feedbackGiven ? (
              <div className="flex items-center gap-1.5 text-xs font-medium text-emerald-400 bg-emerald-950/40 border border-emerald-800/60 px-3 py-1.5 rounded-xl animate-in fade-in">
                <CheckCircle2 className="w-4 h-4" />
                <span>Thank you for your feedback!</span>
              </div>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => handleFeedback("yes")}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-secondary hover:bg-secondary/80 border border-border text-foreground text-xs font-medium transition-colors cursor-pointer"
                >
                  <ThumbsUp className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Yes</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleFeedback("no")}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-secondary hover:bg-secondary/80 border border-border text-foreground text-xs font-medium transition-colors cursor-pointer"
                >
                  <ThumbsDown className="w-3.5 h-3.5 text-rose-400" />
                  <span>No</span>
                </button>
              </>
            )}
          </div>
        </div>

        {/* Previous / Next Chapter Navigation */}
        <div className="mt-8 pt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {prevPage ? (
            <Link
              to={prevPage.href}
              className="flex items-center gap-3 p-4 rounded-2xl border border-border bg-card hover:border-primary/40 transition-all text-left group shadow-xs"
            >
              <div className="w-8 h-8 rounded-xl bg-secondary flex items-center justify-center text-muted-foreground group-hover:text-primary transition-colors shrink-0">
                <ArrowLeft className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">
                  Previous Chapter
                </div>
                <div className="text-sm font-semibold text-foreground truncate group-hover:text-primary transition-colors">
                  {prevPage.title}
                </div>
              </div>
            </Link>
          ) : (
            <div />
          )}

          {nextPage && (
            <Link
              to={nextPage.href}
              className="flex items-center justify-end text-right gap-3 p-4 rounded-2xl border border-border bg-card hover:border-primary/40 transition-all group shadow-xs"
            >
              <div className="min-w-0">
                <div className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">
                  Next Chapter
                </div>
                <div className="text-sm font-semibold text-foreground truncate group-hover:text-primary transition-colors">
                  {nextPage.title}
                </div>
              </div>
              <div className="w-8 h-8 rounded-xl bg-secondary flex items-center justify-center text-muted-foreground group-hover:text-primary transition-colors shrink-0">
                <ArrowRight className="w-4 h-4" />
              </div>
            </Link>
          )}
        </div>
      </div>
    </motion.main>
  );
}
