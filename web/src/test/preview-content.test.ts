import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
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
    const apiPage = readFileSync(new URL("../pages/ApiReference.tsx", import.meta.url), "utf8");
    expect(apiPage).toContain("No hosted registry API is available");
    expect(apiPage).not.toContain("/v1/packages");
  });

  it("keeps privacy statements tied to browser behavior in the source", () => {
    const privacyPage = readFileSync(new URL("../pages/PrivacyPolicy.tsx", import.meta.url), "utf8");
    expect(privacyPage).toContain("sotlas_feedback_<page>");
    expect(privacyPage).not.toContain("TasteTrack");
    expect(privacyPage).not.toContain("compile latency telemetry");
  });

  it("loads website examples from the files exercised by CI", () => {
    const playground = readFileSync(new URL("../pages/Playground.tsx", import.meta.url), "utf8");
    expect(playground).toContain("../../../examples/01_hello_systems/main.sotlas?raw");
    expect(playground).toContain("../../../examples/07_cli_tool/main.sotlas?raw");
    expect(playground).not.toContain("Simulated");
  });

  it("does not present the retired Studio page as a hosted compiler", () => {
    const studio = readFileSync(new URL("../../public/studio/index.html", import.meta.url), "utf8");
    expect(studio).toContain("does not provide a browser compiler");
    expect(studio).not.toContain("/api/compile");
    expect(studio).not.toContain("function runCode()");
  });
});
