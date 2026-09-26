export interface ChangelogSection {
  title: string;
  items: string[];
  code?: { lines: string[] };
}

export interface ChangelogBadge {
  variant: "features" | "improvements" | "fixes";
  label: string;
}

export interface ChangelogEntryData {
  date: string;
  badges: ChangelogBadge[];
  sections: ChangelogSection[];
}

export const changelogData: ChangelogEntryData[] = [
  {
    date: "Development snapshot · September 26, 2026",
    badges: [
      { variant: "improvements", label: "Preview" },
      { variant: "fixes", label: "Compiler and CI" },
    ],
    sections: [
      {
        title: "Preview workflow",
        items: [
          "CI packages the VS Code extension as a downloadable preview VSIX.",
          "The native `sotlas run` command builds in a temporary directory and removes its executable after it exits.",
          "The command-dispatch example is checked and emitted through the canonical frontend and C11 backend.",
          "The LLVM backend rejects unsupported SIR instructions before code generation.",
        ],
      },
      {
        title: "Release status",
        items: [
          "This is a development snapshot, not a published Sotlas 1.0 release.",
          "The repository commit history and CI results are the current record of changes.",
        ],
      },
    ],
  },
];
