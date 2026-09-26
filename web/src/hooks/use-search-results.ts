import { useMemo } from "react";
import { FileText, Clock, type LucideIcon } from "lucide-react";
import { documentationPages } from "@/data/documentation-pages";
import { changelogData } from "@/data/changelog";

export interface SearchResult {
  id: string;
  title: string;
  description: string;
  href: string;
  category: "docs" | "changelog";
  icon: LucideIcon;
}

export function useSearchResults(query: string): SearchResult[] {
  return useMemo(() => {
    if (!query || query.trim().length < 2) {
      return [];
    }

    const searchTerm = query.toLowerCase().trim();
    const results: SearchResult[] = [];

    // Search documentation pages
    Object.entries(documentationPages).forEach(([slug, page]) => {
      const titleMatch = page.title.toLowerCase().includes(searchTerm);
      const descMatch = page.description.toLowerCase().includes(searchTerm);
      const contentMatch = page.sections.some(
        (section) =>
          section.title.toLowerCase().includes(searchTerm) ||
          section.content.toLowerCase().includes(searchTerm) ||
          section.listItems?.some((item) => item.toLowerCase().includes(searchTerm))
      );

      if (titleMatch || descMatch || contentMatch) {
        results.push({
          id: `doc-${slug}`,
          title: page.title,
          description: page.description,
          href: `/docs/${slug}`,
          category: "docs",
          icon: FileText,
        });
      }
    });

    // Search changelog entries
    changelogData.forEach((entry, index) => {
      const sectionsMatch = entry.sections.some(
        (section) =>
          section.title.toLowerCase().includes(searchTerm) ||
          section.items.some((item) => item.toLowerCase().includes(searchTerm))
      );

      if (sectionsMatch) {
        // Find the matching section for a better title
        const matchingSection = entry.sections.find(
          (section) =>
            section.title.toLowerCase().includes(searchTerm) ||
            section.items.some((item) => item.toLowerCase().includes(searchTerm))
        );

        results.push({
          id: `changelog-${index}`,
          title: matchingSection?.title || `Update: ${entry.date}`,
          description: `Changelog from ${entry.date}`,
          href: "/changelog",
          category: "changelog",
          icon: Clock,
        });
      }
    });

    // Limit results per category
    const docsResults = results.filter((r) => r.category === "docs").slice(0, 5);
    const changelogResults = results.filter((r) => r.category === "changelog").slice(0, 3);

    return [...docsResults, ...changelogResults];
  }, [query]);
}
