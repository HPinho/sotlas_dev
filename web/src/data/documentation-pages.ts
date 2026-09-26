export interface DocPageCode {
  lines: string[];
  caption?: string;
}

export interface DocPageSection {
  id: string;
  title: string;
  level: "h2" | "h3";
  content: string;
  listItems?: string[];
  orderedList?: boolean;
  code?: DocPageCode;
}

export interface DocPageContent {
  title: string;
  description: string;
  breadcrumb: string[];
  sections: DocPageSection[];
}

type SectionInput = Omit<DocPageSection, "id" | "level">;

function page(
  title: string,
  description: string,
  breadcrumb: string[],
  sections: SectionInput[],
): DocPageContent {
  return {
    title,
    description,
    breadcrumb,
    sections: sections.map((section, index) => ({
      ...section,
      id: `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${index + 1}`,
      level: "h2" as const,
    })),
  };
}

const previewScope =
  "This page describes the current Sotlas 1.0 preview candidate in this repository. A syntax form or library module is not a support promise by itself. The release scope and passing CI gates define the accepted subset.";

const releaseLinks = [
  "Repository: https://github.com/HPinho/sotlas_dev",
  "Release scope: docs/sotlas_1_0_release_scope.md",
  "Phase status: docs/sotlas_implementation_status.md",
  "Master roadmap: docs/sotlas_master_roadmap.md",
];

export const documentationPages: Record<string, DocPageContent> = {
  overview: page("Sotlas Preview", "A bounded systems-language preview with explicit ownership rules, a canonical compiler frontend, and checked C11 and LLVM paths.", ["Getting Started", "Overview"], [
    { title: "What works today", content: "Sotlas is an experimental systems programming language. The current preview is useful for exploring its parser, static checks, ownership model, and a limited set of native programs. The public contract is deliberately narrower than the full roadmap.", listItems: ["The canonical `sotlas check` command validates accepted source programs.", "The C11 backend emits code for its documented subset.", "The LLVM backend lowers a smaller checked SIR subset and rejects unsupported forms.", "Ownership domains have individual contracts; support in one domain does not imply support for every combination or backend."] },
    { title: "Start with a checked example", content: "Clone the development repository and use the installed Python package from the checkout. These commands are also exercised by CI.", code: { caption: "PowerShell or a POSIX shell", lines: ["git clone https://github.com/HPinho/sotlas_dev.git", "cd sotlas_dev", "python -m pip install -e .", "sotlas check examples/01_hello_systems/main.sotlas", "sotlas run examples/01_hello_systems/main.sotlas"] } },
    { title: "Read the support contract", content: previewScope, listItems: releaseLinks },
  ]),
  guarantees: page("Checked Guarantees", "What the Sotlas preview checks, what its backends emit, and where its guarantees stop.", ["Getting Started", "Guarantees"], [
    { title: "Compiler checks", content: "The installed CLI uses the canonical frontend. Accepted source is parsed, type checked, and checked against safety and ownership rules before the selected backend runs. Unsupported shapes should fail with an error rather than receive guessed lowering.", listItems: ["A successful `check` means the canonical frontend accepted the file; it does not prove runtime behavior or hardware correctness.", "C11 and LLVM have different supported subsets.", "Prototype inspection commands are not production lowering contracts."] },
    { title: "Evidence and limits", content: "A feature is stable only for the subset described in the release scope and covered by the corresponding tests. The master roadmap includes broader design work that is not part of the current preview contract.", listItems: releaseLinks },
  ]),
  profiles: page("Compilation Targets", "Current target and backend behavior, with commands that can be checked against this repository.", ["Getting Started", "Targets"], [
    { title: "Backends", content: "The preview offers C11 emission from the canonical source frontend and direct LLVM lowering from checked SIR. The LLVM path is narrower; unsupported instructions or types are rejected. Target names accepted by the CLI do not imply that each target can produce a complete executable.", listItems: ["Choose C11 explicitly with `--backend c11`.", "Choose LLVM explicitly with `--backend llvm`.", "Consult `sotlas target-report` and the release scope for the target contract."] },
    { title: "Hardware targets", content: "Hardware-oriented syntax and runtime modules are still preview work. A source example or target name does not establish that a real board, peripheral, interrupt path, or device runtime has been validated." },
  ]),
  installation: page("Installation", "Build the compiler from the development checkout and verify the installed command.", ["Getting Started", "Installation"], [
    { title: "Requirements", content: "The current compiler is distributed from this source repository as a Python package. A native C compiler is required for `sotlas run` and native C11 tests. LLVM-based commands also require the toolchain described by the repository's CI configuration.", listItems: ["Python 3.10 or newer.", "Git to clone the development checkout.", "GCC or Clang for native C11 execution."] },
    { title: "Install from source", content: "There is no standalone `sot` installer or self-contained native compiler binary in this preview. Install the checked-out package with pip:", code: { caption: "Install the preview", lines: ["git clone https://github.com/HPinho/sotlas_dev.git", "cd sotlas_dev", "python -m pip install -e .", "sotlas version"] } },
    { title: "Verify the compiler", content: "Run a source check, then compile and execute the included example:", code: { caption: "Verify", lines: ["sotlas check examples/01_hello_systems/main.sotlas", "sotlas run examples/01_hello_systems/main.sotlas"] } },
  ]),
  "vscode-tutorial": page("VS Code Setup", "Install the Sotlas language extension and point it at a compiler from this checkout.", ["Getting Started", "VS Code"], [
    { title: "Build the extension", content: "The repository contains the extension source under `editors/vscode`. CI compiles and packages a VSIX, installs it into a clean VS Code profile, and checks that source-located compiler diagnostics reach the Problems collection. Install the Sotlas compiler separately; the extension invokes the configured compiler command.", code: { caption: "From the repository root", lines: ["cd editors/vscode", "npm install", "npm test", "npx @vscode/vsce package --out sotlas-preview.vsix", "npm run test:vsix"] } },
    { title: "Configure and check", content: "Set `sotlas.compilerPath` to the installed `sotlas` command or its full executable path. Open a `.sotlas` file and run `Sotlas: Check Active File`. Compiler diagnostics with source locations appear in the Problems panel; structural hints are marked as extension diagnostics." },
    { title: "Preview limits", content: "The extension is in preview. Syntax highlighting, local structural hints, outline, hover, and compiler commands are available. The optional LSP mode requires an installed compiler with the `lsp --stdio` command. Formatting is performed by the CLI and may rewrite the source file." },
  ]),
  "first-program": page("First Program", "Check, compile, and execute a small Sotlas program from the repository.", ["Getting Started", "First Program"], [
    { title: "Use a repository example", content: "The checked-in hello systems example is accepted by the canonical frontend and returns an exit status that can be used for a native smoke test.", code: { caption: "Run the example", lines: ["sotlas check examples/01_hello_systems/main.sotlas", "sotlas compile examples/01_hello_systems/main.sotlas --backend c11 --emit-c -o hello.c", "sotlas run examples/01_hello_systems/main.sotlas"] } },
    { title: "What this proves", content: "A successful run proves that this particular source passed the compiler, generated C compiled with the local toolchain, and the resulting process returned successfully. It does not demonstrate terminal I/O, packaging, or broad standard-library support." },
  ]),
  tools: page("Compiler Commands", "CLI commands included in the current source build and their maturity boundaries.", ["Getting Started", "Tools"], [
    { title: "Core workflow", content: "These commands operate on the canonical compiler path:", listItems: ["`sotlas check FILE` validates a source file without writing output.", "`sotlas compile FILE --backend c11 --emit-c -o FILE.c` emits C11.", "`sotlas run FILE` compiles and runs a native program using a C compiler.", "`sotlas version` prints the installed package version."] },
    { title: "Inspection and project commands", content: "Commands such as `dump-sir`, Studio, package management, formatting, and reporting have individual limits. See `sotlas --help` and the release scope. In particular, `dump-sir` is a prototype view and must not be confused with the checked canonical SIR report." },
  ]),
  syntax: page("Syntax and Declarations", "Use the checked examples and language specification as the syntax reference for the preview.", ["Language", "Syntax"], [
    { title: "Reference sources", content: "The grammar and syntax are evolving. The specification describes intended language forms, while `sotlas check` and the passing parser tests describe what this build accepts.", listItems: ["Specification: `docs/language_spec.md`.", "Parser tests: `tests/test_sotlas_parser.py` and related frontend tests.", "Runnable examples: `examples/manifest.json`; each entry has an explicit maturity label."] },
    { title: "Example", content: "This module is checked by the current CI example gate:", code: { caption: "examples/07_cli_tool/main.sotlas", lines: ["module examples::cli_tool;", "", "pub enum Command {", "    None = 0,", "    Build = 1,", "    Test = 2,", "    Help = 3", "}", "", "pub fn parse_command(arg: u32) -> Command {", "    if arg == 1 { return Command::Build; }", "    if arg == 2 { return Command::Test; }", "    if arg == 3 { return Command::Help; }", "    return Command::None;", "}"] } },
  ]),
  types: page("Types and Bounds", "Primitive, aggregate, pointer, and bounded-type support varies by compiler path.", ["Language", "Types"], [
    { title: "Use the checked subset", content: "The canonical parser and type checker accept a defined source subset. Backend acceptance can be narrower than frontend acceptance, especially for LLVM lowering. Use the tests and release scope before depending on a type in emitted code." },
    { title: "Failure behavior", content: "If a type or layout has no implementation in the selected backend, compilation should stop with an unsupported-lowering diagnostic. Do not infer target layout or ABI compatibility from the spelling of a type." },
  ]),
  "specs-classes": page("Specs, Structs, and Classes", "Aggregate types and contracts are evolving; verify behavior against the canonical compiler and release tests.", ["Language", "Types"], [
    { title: "Preview support", content: "Structs, enums, and class-related ownership work have test coverage in specific subsets. That evidence does not establish universal generic, layout, inheritance, deinitialization, or backend support." },
    { title: "Contract source", content: "The implementation status and release scope identify tested source forms. Broader design material in the master roadmap remains roadmap material until it passes its feature gate.", listItems: releaseLinks },
  ]),
  functions: page("Functions and Modules", "Module and function behavior is defined by the canonical frontend, CLI integration tests, and backend contracts.", ["Language", "Functions"], [
    { title: "Source compilation", content: "The compiler accepts functions and module declarations in its supported source subset. The `check` command validates frontend acceptance; C11 and LLVM compilation apply their own lowering limits." },
    { title: "Build and linking", content: "Package builds, cross-module linking, stable symbol naming, and general foreign ABI compatibility have separate scope. The presence of an `import`, `pub`, or `extern` declaration does not guarantee every dependency or ABI shape is linkable." },
  ]),
  concurrency: page("Concurrency and Islands", "Concurrency and ownership domains have bounded, test-backed support; general scheduling is not implied.", ["Language", "Concurrency"], [
    { title: "Ownership domains", content: "The 1.0 release scope records the certified subsets for `island`, `quarantine`, `handover`, `direct`, and `whisper`. Unsupported transitions and escape shapes remain rejected or outside the contract." },
    { title: "Runtime behavior", content: "A static domain model or reference runtime is not proof of general thread scheduling, device synchronization, data-race freedom for arbitrary programs, or cross-backend equivalence. See the domain-specific gates before relying on a behavior." },
  ]),
  memory: page("Ownership and Memory", "The Sotlas ownership model is tested in subsets; the master roadmap tracks broader cases still open.", ["Language", "Memory"], [
    { title: "Domain contract", content: "The preview tracks exclusive ownership (`sole`), shared ownership, scoped regions, and additional borrow or isolation domains. Each has a separate accepted subset. A keyword being recognized does not make every storage, return, alias, or control-flow form safe or supported." },
    { title: "Safe use", content: "Start with the release scope and its named CI tests. Unsupported forms should be rejected. Report any accepted program that violates its tested ownership or cleanup contract as a compiler bug.", listItems: ["Release scope: `docs/sotlas_1_0_release_scope.md`.", "Phase 2 gates: `tests/test_sotlas_phase2_v1_region_release_gate.py` and `tests/test_sotlas_phase2_v1_borrow_release_gate.py`.", "Shared ownership gates and limits are listed in `docs/sotlas_master_roadmap.md`."] },
  ]),
  pointers: page("Pointer Domains", "Hardware-oriented pointer types are part of the language design; their end-to-end implementation remains bounded.", ["Low-Level", "Pointers"], [
    { title: "Preview boundary", content: "Pointer parsing, semantic checks, volatile or topology-aware lowering, and actual hardware access are distinct capabilities. The historical compiler and canonical compiler do not have identical contracts. Verify the selected frontend and backend before using a pointer domain." },
    { title: "Hardware use", content: "No code shown in this documentation should be treated as safe to run on real hardware without a matching board, address map, target ABI, and runtime validation. The hardware and device items remain preview or planned work in the release scope." },
  ]),
  hardware: page("Hardware Features", "Hardware syntax and compiler support are not the same as a validated hardware runtime.", ["Low-Level", "Hardware"], [
    { title: "What is available", content: "The repository contains experiments and tests for processor intrinsics, pointer domains, interrupts, and device lifecycle. Their status differs by frontend, backend, and target. The release scope labels hardware-oriented domains outside the stable 1.0 contract as preview." },
    { title: "Before using a device", content: "Check target-report output, the hardware tests, and the relevant phase scope. Never infer that a sample performs real MMIO or that an interrupt handler is safe on a target solely because source parsing succeeds." },
  ]),
  "bit-slicing": page("Bit Operations and Layout", "Bit operations and layout features need target-specific checks before they can be used in hardware code.", ["Low-Level", "Bit Operations"], [
    { title: "Current contract", content: "The repository contains parser, semantic, and historical code-generation tests for bit operations and layout. That does not imply the installed canonical path accepts every form or that results match every target ABI. Use the canonical test suite and selected backend as the source of truth." },
    { title: "Reference", content: "See `tests/test_sotlas_layout_intrinsics.py`, `tests/test_sotlas_hardware_simd_050.py`, and the relevant feature sections in `docs/sotlas_master_roadmap.md`. Historical migration tests are not sufficient release evidence on their own." },
  ]),
  compiler: page("Compiler Pipeline", "The installed frontend and the checked backend paths are distinct from prototype compiler views.", ["Compiler", "Architecture"], [
    { title: "Canonical path", content: "The installed CLI uses `compiler/sotlas_compile`. `sotlas check` and `sotlas compile` share the canonical source acceptance pipeline. C11 emission uses that source pipeline. LLVM lowers the verified canonical SIR subset directly." },
    { title: "Experimental tools", content: "`dump-sir` is a prototype view. `sir-report` inventories validated canonical SIR. Emitting a report or intermediate representation is not equivalent to producing and executing a supported native program." },
    { title: "Validation", content: "The CI workflow runs the Python suite, explicit backend contracts, packaging smoke tests, and a preview extension build. The status in this repository records the latest development evidence; old workflow runs are not evidence for a newer commit." },
  ]),
  interoperability: page("C Interoperability", "Foreign-function and C layout support are bounded and do not constitute a stable general ABI.", ["Compiler", "Interoperability"], [
    { title: "Preview contract", content: "The compiler has FFI and C-layout implementation work with targeted tests. The 1.0 preview does not promise a frozen ABI, arbitrary header import, broad C++ interoperability, or general safe wrappers." },
    { title: "Validation", content: "Use `docs/sotlas_1_0_release_scope.md` and `tests/test_sotlas_unsafe_ffi.py` for current supported boundaries. Link the foreign object using a documented test case before depending on an ABI shape." },
  ]),
  stdlib: page("Standard Library", "The repository includes Sotlas library modules with varying levels of parser, type-check, and runtime evidence.", ["Compiler", "Standard Library"], [
    { title: "Core modules", content: "The `stdlib/` tree contains modules for memory, allocation, strings, slices, options, results, collections, formatting, and other areas. File presence is not a stability or runtime-support claim.", listItems: ["`tests/test_sotlas_stdlib.py` parses, type checks, and emits selected core modules.", "`tests/test_sotlas_foundation_essentials.py` covers selected foundation modules.", "Native runtime behavior requires an explicit end-to-end test for that module and backend."] },
    { title: "Ownership and allocation", content: "Some APIs expose raw pointers and caller-managed allocation. Follow each function's return values and cleanup requirements. For example, the current string buffer API exposes `string_deinit`; automatic destruction of returned strings is not claimed by its source comments." },
    { title: "Contribute a library test", content: "A useful addition should cover ordinary inputs, empty inputs, invalid pointers or capacities where relevant, allocator failure, and cleanup. Prefer a native test that checks observable results over a test that only checks emitted symbol names." },
  ]),
  keywords: page("Keyword Reference", "Language keywords are defined by the specification and may have different implementation maturity.", ["Specification", "Keywords"], [
    { title: "Do not infer support from spelling", content: "A token, syntax highlight, or roadmap entry only shows that a word is known to the language project. It does not establish parser acceptance, type rules, lowering, runtime behavior, or stable support." },
    { title: "Check a feature", content: "For each keyword, consult its phase scope, the current implementation status, and tests that execute the canonical compiler path. The roadmap separates intended semantics from implemented contracts.", listItems: releaseLinks },
  ]),
  community: page("Contributing", "Help improve the preview by reporting reproducible behavior and test-backed documentation corrections.", ["Community", "Contributing"], [
    { title: "Useful reports", content: "Include the commit or package version, operating system, backend, exact command, smallest source file that reproduces the issue, and the complete diagnostic. Do not include secrets or proprietary source." },
    { title: "Changes to the preview", content: "Keep claims tied to tests. A new language feature should include accepted cases, rejected cases, backend behavior, and an executable example when the runtime supports it. Documentation and site updates should be written in English for the current preview." },
    { title: "Project links", content: "Development repository: https://github.com/HPinho/sotlas_dev. Organization repositories and the live website will be updated after changes in this development repository are reviewed." },
  ]),
};

export const SLUG_ALIASES: Record<string, string> = {
  interoperabilidade: "interoperability", sintaxe: "syntax", tipos: "types",
  memoria: "memory", ponteiros: "pointers", compilador: "compiler",
  comunidade: "community", perfis: "profiles", instalacao: "installation",
  "primeiro-programa": "first-program", ferramentas: "tools",
  "palavras-chave": "keywords", funcoes: "functions",
  concorrencia: "concurrency", garantias: "guarantees",
};

export function getDocPage(slug: string): DocPageContent | undefined {
  return documentationPages[SLUG_ALIASES[slug] || slug];
}

export function generateTableOfContents(slug: string) {
  const pageContent = getDocPage(slug);
  return pageContent?.sections.map(({ id, title, level }) => ({ id, title, level })) || [];
}
