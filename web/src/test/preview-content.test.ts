import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { navigationGroups } from "@/data/documentation";
import { documentationPages, getDocPage } from "@/data/documentation-pages";

describe("preview documentation", () => {
  it("provides a page for every documentation navigation link", () => {
    const links = navigationGroups.flatMap((group) => group.items);
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) {
      const slug = link.href.replace(/^\/docs\//, "");
      expect(getDocPage(slug), `${link.href} should resolve`).toBeDefined();
    }
  });

  it("states backend and hardware boundaries on the support pages", () => {
    const overview = getDocPage("overview");
    const targets = getDocPage("profiles");
    const hardware = getDocPage("hardware");
    const text = [overview, targets, hardware]
      .flatMap((page) => page?.sections.map((section) => `${section.title} ${section.content} ${(section.listItems || []).join(" ")}`) || [])
      .join(" ")
      .toLowerCase();

    expect(text).toContain("c11");
    expect(text).toContain("llvm");
    expect(text).toContain("preview");
    expect(text).toContain("hardware");
  });

  it("does not advertise the old installer or unmeasured zero-cost claims", () => {
    const installation = getDocPage("installation");
    const siteCopy = Object.values(documentationPages)
      .flatMap((page) => page?.sections.map((section) => `${section.content} ${(section.listItems || []).join(" ")}`) || [])
      .join(" ")
      .toLowerCase();

    expect(installation?.sections.map((section) => section.content).join(" ")).toContain("no standalone");
    expect(siteCopy).not.toContain("https://sotlas.dev/install.sh");
    expect(siteCopy).not.toContain("zero-cost destruction");
  });

  it("does not expose registry routes that the preview does not implement", () => {
    const apiPage = readFileSync(resolve(process.cwd(), "src/pages/ApiReference.tsx"), "utf8");
    expect(apiPage).toContain("No hosted registry API is available");
    expect(apiPage).not.toContain("/v1/packages");
  });

  it("keeps privacy statements tied to browser behavior in the source", () => {
    const privacyPage = readFileSync(resolve(process.cwd(), "src/pages/PrivacyPolicy.tsx"), "utf8");
    expect(privacyPage).toContain("sotlas_feedback_<page>");
    expect(privacyPage).not.toContain("TasteTrack");
    expect(privacyPage).not.toContain("compile latency telemetry");
    const cookieSettings = readFileSync(resolve(process.cwd(), "src/components/cookie-manager/CookiePreferencesManager.tsx"), "utf8");
    expect(cookieSettings).toContain("does not load analytics or compiler telemetry");
    expect(cookieSettings).not.toContain("WebAssembly compiler runtime benchmarking data");
    expect(cookieSettings).toContain("Not collected");
    expect(cookieSettings).not.toContain("aria-checked={prefs.performance}");
  });

  it("loads website examples from the files exercised by CI", () => {
    const playground = readFileSync(resolve(process.cwd(), "src/pages/Playground.tsx"), "utf8");
    expect(playground).toContain("../../../examples/01_hello_systems/main.sotlas?raw");
    expect(playground).toContain("../../../examples/07_cli_tool/main.sotlas?raw");
    expect(playground).not.toContain("Simulated");
  });

  it("does not present the retired Studio page as a hosted compiler", () => {
    const studio = readFileSync(resolve(process.cwd(), "public/studio/index.html"), "utf8");
    expect(studio).toContain("does not provide a browser compiler");
    expect(studio).not.toContain("/api/compile");
    expect(studio).not.toContain("function runCode()");
  });

  it("keeps high-visibility marketing claims within the documented preview contract", () => {
    const publicCopyFiles = [
      "src/data/keywords.ts",
      "src/components/hero/Hero.tsx",
      "src/components/hero/InteractiveCodeHero.tsx",
      "src/components/project-stats/ProjectStats.tsx",
      "src/components/compiler-pipeline/CompilerPipeline.tsx",
      "src/components/code-showcase/codeShowcaseData.ts",
      "src/components/code-showcase/CodeShowcase.tsx",
      "src/components/keywords-glossary/KeywordsGlossary.tsx",
      "src/components/comparison/SotlasVsC.tsx",
      "src/components/comparison-table/ComparisonTable.tsx",
      "src/components/interop-diagram/InteropDiagram.tsx",
      "src/components/pillars/TechnicalPillars.tsx",
    ].map((path) => readFileSync(resolve(process.cwd(), path), "utf8").toLowerCase()).join("\n");

    for (const unsupportedClaim of [
      "mathematically impossible",
      "data races impossible",
      "100% guaranteed",
      "zero-cost destruction",
      "uefi gop framebuffer",
      "interrupt flags atomically masked",
      "freestanding compilation succeeded",
      "used in the baken os kernel",
    ]) {
      expect(publicCopyFiles).not.toContain(unsupportedClaim);
    }
    expect(publicCopyFiles).toContain("simulated output");
    expect(publicCopyFiles).toContain("do not compile or run");
  });
});
