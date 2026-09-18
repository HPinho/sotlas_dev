export interface ChangelogSection {
  title: string;
  items: string[];
  code?: {
    lines: string[];
  };
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
    date: "Sotlas 0.5.1 — September 16, 2026",
    badges: [
      { variant: "fixes", label: "Fixes" },
      { variant: "improvements", label: "Ecosystem" },
    ],
    sections: [
      {
        title: "Extension & Installation Documentation",
        items: [
          "Removed internal build commands from user guides in the extension marketplace.",
          "Streamlined installation instructions for VS Code and Open VSX (`ext install sotlas-lang.vscode-sotlas`).",
          "Standardized documentation for official community distribution.",
        ],
      },
    ],
  },
  {
    date: "Sotlas 0.5.0 — September 16, 2026",
    badges: [
      { variant: "features", label: "Features" },
      { variant: "improvements", label: "Hardware & SIMD" },
    ],
    sections: [
      {
        title: "Declarative MMIO Registers & SIMD",
        items: [
          "Native support for declarative hardware registers with deterministic bit-field mapping (`register Reg: u32`).",
          "Freestanding SIMD vector types for high-performance computing (`f32x4`, `f32x8`, `u8x16`, `i32x4`, `i64x2`).",
          "Support for comptime `mould` blocks and static `probe` assertions.",
          "Official Language Server Protocol integration (`sotlas lsp --stdio`).",
        ],
        code: {
          lines: [
            "// Declarative hardware MMIO register",
            "register ControlReg: u32 {",
            "    enable: 0..0;",
            "    mode:   1..3;",
            "    irq_en: 4..4;",
            "}",
            "",
            "let regs = 0x4000_1000 as *rawphys ControlReg;",
            "regs.enable = true;",
          ],
        },
      },
    ],
  },
  {
    date: "Sotlas 0.4 — September 2, 2026",
    badges: [
      { variant: "features", label: "Features" },
      { variant: "improvements", label: "Improvements" },
    ],
    sections: [
      {
        title: "Language & Topology",
        items: [
          "Introduced Topology Pointers (`*rawphys`, `*virtmap`, `*portwire`, `*dmazone`).",
          "Native support for atomic critical sections with `clinch` and guaranteed `revert`.",
          "Zero-cost `.slit[start..end]` bit-slicing and `.strand` endianness reversal operators.",
        ],
        code: {
          lines: [
            "pub fn read_phys_byte(addr: *rawphys UInt8) -> UInt8 {",
            "    clinch {",
            "        return *addr;",
            "    } revert {",
            "        rebound;",
            "    }",
            "}",
          ],
        },
      },
      {
        title: "Compiler & Profiles",
        items: [
          "Stabilized `target barecore;` profile for kernels and freestanding firmware.",
          "New `riscv64-none-elf` target and incremental spec compilation with AST hashing.",
          "Diagnostic SRG error messages with actionable `handover` or `quarantine` hints.",
        ],
      },
    ],
  },
  {
    date: "Sotlas 0.3 — June 14, 2026",
    badges: [
      { variant: "features", label: "Features" },
      { variant: "fixes", label: "Fixes" },
    ],
    sections: [
      {
        title: "Concurrency & SRG",
        items: [
          "Isolated memory regions via `island` and `quarantine` primitives.",
          "Static verification of zero data races in the SRG graph.",
          "`await` enabled in functions marked with `async` across native and web profiles.",
        ],
      },
      {
        title: "Fixes",
        items: [
          "Precise static cycle resolution for `co-owned` types in AST lowering.",
          "Exact alignment guarantees for `mesh` structures on 32-bit and 64-bit buses.",
        ],
      },
    ],
  },
  {
    date: "Sotlas 0.2 — March 3, 2026",
    badges: [{ variant: "features", label: "Features" }],
    sections: [
      {
        title: "Specification & Contracts",
        items: [
          "Formal introduction of `spec` and `adopts` replacing C-style header files.",
          "Compile-time bounds verification for `BoundedType` (`Type.bound[min..max]`).",
          "Processor-native interrupt service routine support via `trapfn`.",
        ],
      },
    ],
  },
];
