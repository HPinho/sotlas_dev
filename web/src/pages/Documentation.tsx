import { useParams, Navigate } from "react-router-dom";
import { Navbar } from "@/components/navbar";
import { DocSidebar, DocTableOfContents } from "@/components/documentation";
import { DocPageContent } from "@/components/documentation/DocPageContent";
import { Footer } from "@/components/footer";
import { generateTableOfContents, getDocPage } from "@/data/documentation-pages";
import { Seo } from "@/components/Seo";

export default function Documentation() {
  const params = useParams();
  const pageSlug = params["*"] || "overview";
  const page = getDocPage(pageSlug);
  const tableOfContents = generateTableOfContents(pageSlug);

  // Redirect to default page if no slug provided
  if (!params["*"]) {
    return <Navigate to="/docs/overview" replace />;
  }

  const pageTitle = page?.title || pageSlug.replace(/-/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Seo
        title={`${pageTitle} — Sotlas Documentation`}
        description={page?.description || "Preview documentation for the Sotlas compiler, language subset, supported backends, and known limits."}
        path={`/docs/${pageSlug}`}
      />
      <Navbar />
      <div className="flex pt-16 max-w-[90rem] mx-auto flex-1">
        <DocSidebar />
        <DocPageContent />
        <DocTableOfContents items={tableOfContents} className="pr-6" />
      </div>
      <Footer />
    </div>
  );
}
