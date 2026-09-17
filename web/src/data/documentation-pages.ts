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

export const documentationPages: Record<string, DocPageContent> = {
  overview: {
    title: "Overview",
    description: "Discover Sotlas — a unified compiled programming language engineered for bare-metal, operating systems, and web.",
    breadcrumb: ["Getting Started", "Overview"],
    sections: [
      {
        id: "what-is-sotlas",
        title: "What is Sotlas",
        level: "h2",
        content:
          "Sotlas is a general-purpose compiled language designed to bridge high-level software expressiveness with surgical hardware control. It eliminates the traditional divide between application languages and systems languages, allowing developers to write everything from device drivers to high-throughput microservices and web applications with the same unified syntax and static compile-time guarantees.",
        code: {
          caption: "Example — target barecore and register manipulation",
          lines: [
            "target barecore;",
            "module kernel::timer;",
            "",
            "mesh PitRegisters {",
            "    channel0: UInt8 align(1);",
            "    command:  UInt8 align(1);",
            "}",
            "",
            "pub fn init_timer(hz: UInt32) -> Void {",
            "    clinch {",
            "        let pit = 0x40 as *portwire PitRegisters;",
            "        pit.command = 0x36;",
            "        let divisor = (1193182 / hz).slit[0..15];",
            "        pit.channel0 = divisor.slit[0..7] as UInt8;",
            "        pit.channel0 = divisor.slit[8..15] as UInt8;",
            "    } revert {",
            "        gate(hz > 0) { return; }",
            "    }",
            "}",
          ],
        },
      },
      {
        id: "pillars",
        title: "The Three Core Pillars",
        level: "h2",
        content: "The Sotlas architecture is built upon three fundamental normative innovations:",
        listItems: [
          "Unified Target Profiles: The compiler adapts its instruction set and static constraints based on target (barecore, native, or web) without altering base syntax or modules.",
          "SRG (Scoped Reference Graph): Zero-cost deterministic memory management. Replaces the traditional garbage collector with exclusive lexical ownership (sole), scoped shared graphs (co-owned), and isolated concurrency regions (island).",
          "Topology Pointers: Architecture-aware typed pointers that understand machine physics (*rawphys, *virtmap, *portwire, *dmazone, and *voidzero).",
        ],
      },
      {
        id: "specs-without-headers",
        title: "Headerless Verifiable Contracts",
        level: "h3",
        content:
          "There are no header files (.h or .hpp) in Sotlas. Public interfaces are declared as 'spec' and implemented by structs and classes using the 'adopts' keyword. The compiler generates and verifies cryptographic hashes of public surfaces for ultra-fast incremental compilation.",
      },
      {
        id: "next-steps",
        title: "Next Steps",
        level: "h2",
        content:
          "Explore compilation profiles to understand how to select between barecore and native, or delve into the SRG memory model to master zero-overhead resource management.",
      },
    ],
  },

  guarantees: {
    title: "Semantic Guarantees & Lowering",
    description: "How the Sotlas compiler enforces formal topology, SRG ownership, and hardware safety constraints directly on the AST.",
    breadcrumb: ["Getting Started", "Semantic Guarantees"],
    sections: [
      {
        id: "architecture-guarantees",
        title: "Formal Systems Language Guarantees",
        level: "h2",
        content:
          "Sotlas was designed so that the type system and AST semantic analysis eliminate entire classes of hardware failures, memory leaks, and data races before any code generation occurs.",
      },
      {
        id: "semantic-pillars",
        title: "The Six Static Verification Pillars",
        level: "h2",
        content: "The compiler performs deterministic, zero-cost checks at compile time:",
        listItems: [
          "1. Memory & Ownership Model (SRG — Scoped Reference Graph): The type system tracks lexical ownership (sole, co-owned, island, whisper, direct) and validates atomic transfers (handover and quarantine), ensuring precise destruction without GC pauses.",
          "2. Hardware Topology Pointers: Physiographic typing (*rawphys, *virtmap, *portwire, *dmazone, *voidzero). The compiler rejects mixing physical bus addresses with virtual memory or I/O ports.",
          "3. Verifiable Bounds (Bounded Types): Native syntax for strict value constraints (PrimitiveType.bound[lo..hi]) checked at compile time.",
          "4. Structured Low-Level Primitives: Built-in statements including clinch/revert (atomic critical sections with guaranteed CPU flag restoration), quench (persistent memory barriers), trapfn (native ISR calling convention), and rebound.",
          "5. First-Class Bit Manipulation: Dedicated operators including .slit[lo..hi] (field bit-slicing), .notch[n] (individual bit extraction), and .strand (instant endianness swap via hardware bswap).",
          "6. Headerless Contracts (spec and adopts): API conformance verification is performed statically and contractually on the AST, without the fragility of text-substitution preprocessors.",
        ],
        code: {
          caption: "Example — Static topology and ownership safety",
          lines: [
            "// The compiler knows *rawphys represents physical device memory",
            "let mmio = 0xFD002000 as *rawphys mut UInt32;",
            "",
            "// Atomic critical section with guaranteed parity restoration",
            "clinch {",
            "    *mmio = 0x01;",
            "} revert {",
            "    rebound;",
            "}",
          ],
        },
      },
      {
        id: "modular-lowering",
        title: "Modular Compiler Lowering",
        level: "h2",
        content:
          "The Sotlas compiler validates semantic consistency and the SRG graph before the lowering stage. The emitted intermediate representation — whether freestanding C99 for bootstrap, LLVM IR, or native ELF and PE/COFF binaries — receives code already purified of ownership and topology violations.",
        code: {
          caption: "Sotlas Compiler Pipeline",
          lines: [
            "Source Code (.sotlas) ",
            "  -> Parser & Unified AST ",
            "  -> Topology Semantic Validator (*rawphys, *dmazone, *portwire)",
            "  -> SRG Ownership Graph Verifier (sole, island, handover, quarantine)",
            "  -> Modular Lowering (Rejects invalid states prior to emission)",
            "  -> Backend (Freestanding C99 / LLVM IR / Native ELF & PE-COFF)",
          ],
        },
      },
    ],
  },

  profiles: {
    title: "Target Profiles",
    description: "How Sotlas adapts compilation rules and APIs across profiles without altering the foundational language.",
    breadcrumb: ["Getting Started", "Target Profiles"],
    sections: [
      {
        id: "concept",
        title: "Profile Architecture",
        level: "h2",
        content:
          "At the beginning of any Sotlas compilation unit, you can declare a target profile. The profile restricts code generation capabilities and enables specialized primitives while strictly preserving the language's parser, grammar, syntax, and type system.",
        code: {
          caption: "Profile Declaration",
          lines: [
            "target barecore; // Or shorthand: barecore;",
            "// or:",
            "target native;",
            "// or:",
            "target web;",
          ],
        },
      },
      {
        id: "profile-barecore",
        title: "target barecore",
        level: "h2",
        content:
          "Tailored for kernels, bootloaders, device drivers, embedded firmware, and freestanding environments without an underlying operating system:",
        listItems: [
          "Enables physical hardware primitives: *rawphys, *portwire, clinch, quench, and trapfn.",
          "Disables standard OS system calls (syscalls).",
          "Enables exact hardware layouts via mesh declarations and bus alignments.",
        ],
      },
      {
        id: "profile-native",
        title: "target native",
        level: "h2",
        content:
          "For applications hosted on standard operating systems (Linux, macOS, Windows). Provides access to filesystem I/O, network sockets, OS threads, and direct native C ABI interoperability.",
      },
      {
        id: "profile-web",
        title: "target web",
        level: "h3",
        content:
          "Targeted for WebAssembly runtimes and browser environments, applying memory sandbox restrictions and seamless integration with browser APIs.",
      },
    ],
  },

  installation: {
    title: "Installation",
    description: "Install the official Sotlas compiler toolchain and set up your development environment.",
    breadcrumb: ["Getting Started", "Installation"],
    sections: [
      {
        id: "requirements",
        title: "System Requirements",
        level: "h2",
        content:
          "The official Sotlas toolchain is distributed as a single self-contained native binary with zero external runtime dependencies.",
        listItems: [
          "Linux: x86_64, aarch64, riscv64 (glibc or musl)",
          "macOS: Apple Silicon (M1/M2/M3/M4) and x86_64 (macOS 12+)",
          "Windows: x86_64 and arm64 (Windows 10/11 or Windows Server)",
        ],
      },
      {
        id: "step-by-step",
        title: "Installing the 'sot' Compiler",
        level: "h2",
        content: "To install the official 'sot' tool, run the installation script in your terminal:",
        code: {
          caption: "Terminal Installation",
          lines: [
            "# Linux & macOS",
            "curl -fsSL https://sotlas.dev/install.sh | sh",
            "",
            "# Windows (PowerShell)",
            "irm https://sotlas.dev/install.ps1 | iex",
          ],
        },
      },
      {
        id: "verification",
        title: "Verifying the Installation",
        level: "h3",
        content: "Confirm that the compiler is operational and inspect supported targets:",
        code: {
          caption: "Terminal",
          lines: [
            "$ sot --version",
            "sotlas 0.5.1 (unified specification; target profiles: barecore, native, web)",
            "",
            "$ sot doctor",
            "[✓] Native compiler OK",
            "[✓] Integrated LLVM/Codegen targets OK",
            "[✓] Barecore profile enabled",
          ],
        },
      },
    ],
  },

  "first-program": {
    title: "First Program",
    description: "Write, compile, and run your first Sotlas application.",
    breadcrumb: ["Getting Started", "First Program"],
    sections: [
      {
        id: "creating-project",
        title: "Creating a New Project",
        level: "h2",
        content: "Bootstrap a new Sotlas project using the official CLI:",
        code: {
          caption: "Terminal",
          lines: [
            "$ sot new hello_sotlas --profile native",
            "$ cd hello_sotlas",
          ],
        },
      },
      {
        id: "source-code",
        title: "Source Code",
        level: "h2",
        content:
          "The main entry file src/main.sot declares the module and application entry point:",
        code: {
          caption: "src/main.sot",
          lines: [
            "target native;",
            "module hello_sotlas::main;",
            "",
            "pub fn main() -> Void {",
            '    let message: String = "Hello, Sotlas — Systems Architecture!";',
            '    let version: Float32 = 0.5;',
            '    print("{message} (v{version})");',
            "}",
          ],
        },
      },
      {
        id: "compiling",
        title: "Compilation and Execution",
        level: "h3",
        content: "Compile in development mode or generate an optimized release binary:",
        code: {
          caption: "Terminal",
          lines: [
            "$ sot run",
            "Hello, Sotlas — Systems Architecture! (v0.5)",
            "",
            "$ sot build --release",
            "[✓] Compilation finished: ./bin/hello_sotlas (142 KB stripped)",
          ],
        },
      },
    ],
  },

  tools: {
    title: "Tools & CLI",
    description: "Explore all commands and flags of the official 'sot' utility.",
    breadcrumb: ["Getting Started", "Tools & CLI"],
    sections: [
      {
        id: "subcommands",
        title: "Official Subcommands",
        level: "h2",
        content: "The 'sot' CLI unifies the full software engineering workflow:",
        listItems: [
          "sot new <name> — creates a new project configured with profile.",
          "sot build — compiles modules and emits executables or static libraries.",
          "sot run — executes the primary entry point.",
          "sot test — runs unit and integration test suites.",
          "sot fmt — formats source code according to the canonical specification.",
          "sot check — fast static AST analysis and SRG graph validation without codegen.",
        ],
      },
      {
        id: "profile-flags",
        title: "Multi-Profile Compilation",
        level: "h3",
        content: "Override or inspect the target profile during build:",
        code: {
          caption: "CLI Commands",
          lines: [
            "sot build --target barecore --arch x86_64",
            "sot build --target native --release",
            "sot build --target web --emit-wasm",
          ],
        },
      },
    ],
  },

  syntax: {
    title: "Syntax & Declarations",
    description: "Grammar structure, modules, imports, variable qualifiers, and control flow.",
    breadcrumb: ["Language", "Syntax & Declarations"],
    sections: [
      {
        id: "module-structure",
        title: "Modules and Imports",
        level: "h2",
        content:
          "Every Sotlas file belongs to a qualified module. Declarations use '::' as scope separator and 'pub' for public visibility:",
        code: {
          caption: "Top-Level Module Structure",
          lines: [
            "module driver::serial::uart;",
            "",
            "pub import core::io::{ * };",
            "import hardware::bus::pci;",
          ],
        },
      },
      {
        id: "variables-qualifiers",
        title: "Variable Declarations and Qualifiers",
        level: "h2",
        content:
          "Variables use 'let' (immutable) or 'var' (mutable), with support for static persistence and safety modifiers:",
        listItems: [
          "shielded: Protected against concurrent corruption and spurious memory bus accesses.",
          "nvkeep: Guarantees retention in non-volatile memory (NVDIMM/FRAM), coordinated with quench barriers.",
          "seal: Permanent post-initialization immutability enforced at runtime.",
        ],
        code: {
          caption: "Declarations with Qualifiers",
          lines: [
            "let baud_rate: UInt32 = 115200;",
            "var counter: Int = 0;",
            "",
            "static shielded var lock_counter: UInt32 = 0;",
            "static nvkeep let crypto_key: [UInt8; 32] = load_key();",
          ],
        },
      },
      {
        id: "control-flow",
        title: "Control Flow Statements",
        level: "h2",
        content:
          "Alongside standard constructs (if, match, while, for in), Sotlas includes guard, gate, and handover:",
        code: {
          caption: "Advanced Control Flow",
          lines: [
            "// Guard with mandatory early return",
            "guard descriptor != nil else {",
            "    return -1;",
            "}",
            "",
            "// Gate: runtime assertion with structured recovery",
            "gate(size <= 4096) {",
            "    log_size_fault();",
            "    return;",
            "}",
            "",
            "// Exhaustive pattern matching",
            "match status {",
            "    .ready => start_processing(),",
            "    .busy => await_interrupt(),",
            "    _ => handle_unknown_error(),",
            "}",
          ],
        },
      },
    ],
  },

  types: {
    title: "Types & Bounded Types",
    description: "The unified Sotlas type system: deterministic primitives, bounded types, optionals, and tuples.",
    breadcrumb: ["Language", "Types & Bounded Types"],
    sections: [
      {
        id: "primitives",
        title: "Deterministic Primitive Types",
        level: "h2",
        content:
          "Primitive types have strictly specified bitwidths to eliminate cross-platform variances:",
        listItems: [
          "Signed integers: Int, Int8, Int16, Int32, Int64, ISize",
          "Unsigned integers: UInt, UInt8, UInt16, UInt32, UInt64, USize",
          "IEEE 754 Floating Point: Float32, Float64",
          "Basics: Bool, Char (Unicode 32-bit scalar), String (immutable UTF-8), Void",
        ],
      },
      {
        id: "bounded-types",
        title: "Bounded Types (Compile-Time Bounds)",
        level: "h2",
        content:
          "Sotlas introduces 'BoundedType' directly into the language grammar (e.g. Type.bound[min..max]). The compiler guarantees values never exceed the declared range, eliminating runtime overflows and redundant bounds checks:",
        code: {
          caption: "Bounded Types Examples",
          lines: [
            "let brightness: UInt8.bound[0..100] = 75;",
            "let tcp_port: UInt16.bound[1..65535] = 8080;",
            "let month: UInt8.bound[1..12] = 9;",
            "",
            "// Compile error if out of bounds:",
            "// let err: UInt8.bound[0..10] = 15; // Error: value exceeds maximum bound",
          ],
        },
      },
      {
        id: "optionals-coalesce",
        title: "Optional Types & Nil Coalescing",
        level: "h3",
        content:
          "There are no unprotected null pointers. Optional types are suffixed with '?' (e.g. String?) and the empty sentinel is 'nil'. The null-coalescing operator '??' provides concise defaults:",
        code: {
          caption: "Optionals and Coalescing",
          lines: [
            "fn find_user(id: Int) -> String? {",
            '    if id == 1 { return "Alice"; }',
            "    return nil;",
            "}",
            "",
            'let name: String = find_user(42) ?? "Guest";',
          ],
        },
      },
    ],
  },

  "specs-classes": {
    title: "Specs, Structs & Classes",
    description: "Verifiable contracts via Specs, memory structures, and object orientation with single inheritance.",
    breadcrumb: ["Language", "Specs, Structs & Classes"],
    sections: [
      {
        id: "specs-contracts",
        title: "Specs — Verifiable API Contracts",
        level: "h2",
        content:
          "A 'spec' is the formal contract of a Sotlas API. Structs and classes adopt the spec using the 'adopts' keyword. Because headers do not exist, the spec serves as the canonical typed interface validated by the compiler:",
        code: {
          caption: "Spec Declaration and Adoption",
          lines: [
            "pub spec DeviceDriver {",
            "    fn initialize() -> Bool;",
            "    fn read_status() -> UInt32;",
            "    irqfree fn reset() -> Void;",
            "}",
            "",
            "pub struct PciController adopts DeviceDriver {",
            "    pub bus: UInt8;",
            "    pub device: UInt8;",
            "",
            "    pub init(b: UInt8, d: UInt8) {",
            "        self.bus = b;",
            "        self.device = d;",
            "    }",
            "",
            "    pub fn initialize() -> Bool { return true; }",
            "    pub fn read_status() -> UInt32 { return 0x01; }",
            "    pub irqfree fn reset() -> Void { }",
            "}",
          ],
        },
      },
      {
        id: "classes-inheritance",
        title: "Classes and Single Inheritance",
        level: "h2",
        content:
          "Classes support direct single inheritance (: BaseClass) combined with multiple spec adoptions, init(...) constructors, and deterministic deinit destructors:",
        code: {
          caption: "Single Inheritance with Spec Adoption",
          lines: [
            "class StreamIO {",
            "    pub var open: Bool;",
            "    init() { self.open = true; }",
            "    deinit { self.close(); }",
            "    pub moldable fn close() -> Void { self.open = false; }",
            "}",
            "",
            "class FileStream : StreamIO adopts DeviceDriver {",
            "    capsule let descriptor: Int32;",
            "",
            "    init(fd: Int32) {",
            "        self.descriptor = fd;",
            "        super.init();",
            "    }",
            "",
            "    pub reshape fn close() -> Void {",
            "        super.close();",
            "    }",
            "}",
          ],
        },
      },
      {
        id: "visibility",
        title: "Visibility Modifiers and Method Overriding",
        level: "h3",
        content: "The grammar defines three visibility modifiers and two method polymorphism specifiers:",
        listItems: [
          "pub: Public access across all external modules.",
          "capsule: Access restricted to the current package or module.",
          "lineage: Visible only within the class inheritance hierarchy.",
          "moldable: Method eligible for dynamic dispatch and overriding.",
          "reshape: Formal, explicit override of a moldable method.",
        ],
      },
    ],
  },

  functions: {
    title: "Functions & Modules",
    description: "Function declarations, irqfree routines, expression bodies, and generic parameters.",
    breadcrumb: ["Language", "Functions & Modules"],
    sections: [
      {
        id: "function-declarations",
        title: "Function Syntax",
        level: "h2",
        content:
          "Functions are introduced with 'fn', declare parameter and return types via '-> Type', and accept block bodies { ... } or concise expression bodies => Expr;",
        code: {
          caption: "Function Variants",
          lines: [
            "// Standard block function",
            "fn add(a: Int32, b: Int32) -> Int32 {",
            "    return a + b;",
            "}",
            "",
            "// Expression-body function (ExprBody)",
            "fn square(x: Float64) -> Float64 => x * x;",
            "",
            "// Generic function with Spec constraint",
            "fn duplicate<T: Numeric>(val: T) -> T => val + val;",
          ],
        },
      },
      {
        id: "irqfree",
        title: "The 'irqfree' Modifier",
        level: "h2",
        content:
          "In systems and barecore environments, the 'irqfree' modifier is statically enforced by the compiler: it guarantees the function is lock-free, performs no heap allocations, and is entirely safe to invoke inside interrupt service routines (ISRs and trapfn).",
        code: {
          caption: "irqfree Function",
          lines: [
            "pub irqfree fn ack_interrupt(irq: UInt8) -> Void {",
            "    let pic_eoi = 0x20 as *portwire UInt8;",
            "    *pic_eoi = 0x20;",
            "}",
          ],
        },
      },
      {
        id: "typealias",
        title: "Typealiases",
        level: "h3",
        content:
          "The 'typealias' keyword defines parameterized synonyms for architectural clarity:",
        code: {
          caption: "typealias",
          lines: [
            "typealias PacketBuffer = [UInt8; 1500];",
            "typealias HandlerCallback = (code: Int32) -> Void;",
          ],
        },
      },
    ],
  },

  concurrency: {
    title: "Concurrency & Islands",
    description: "Data-race-free concurrent execution via isolated 'island' memory regions.",
    breadcrumb: ["Language", "Concurrency & Islands"],
    sections: [
      {
        id: "island-memory",
        title: "Data-Race-Free 'island' Regions",
        level: "h2",
        content:
          "The Sotlas concurrency model is anchored by the 'island' modifier. A value marked as 'island' inhabits a completely isolated memory region. Mutable state sharing across threads or CPU cores is statically forbidden:",
        code: {
          caption: "Concurrency Isolation with island",
          lines: [
            "fn process_parallel(data: sole [Int; 1024]) -> Void {",
            "    // Isolate data for concurrent dispatch",
            "    quarantine data;",
            "    // Data is now an 'island', safe for concurrent execution without races",
            "}",
          ],
        },
      },
      {
        id: "async-await",
        title: "Asynchronous Functions (async / await)",
        level: "h2",
        content:
          "Functions marked with 'async' suspend execution without blocking threads via 'await'. In the native profile, this integrates with event-driven OS runtimes; in barecore, it compiles to zero-cost cooperative state machines.",
        code: {
          caption: "async / await",
          lines: [
            "pub async fn read_sensor() -> Float32 {",
            "    let raw = await i2c_request(0x48);",
            "    return (raw as Float32) * 0.0625;",
            "}",
          ],
        },
      },
    ],
  },

  memory: {
    title: "SRG (Scoped Reference Graph)",
    description: "Zero-cost deterministic memory management derived from AST lexical scope without a garbage collector.",
    breadcrumb: ["Low-Level & Hardware", "SRG Memory Graph"],
    sections: [
      {
        id: "srg-concept",
        title: "What is the SRG",
        level: "h2",
        content:
          "The Scoped Reference Graph (SRG) is the native ownership engine of Sotlas. Unlike tracing garbage collectors that pause execution or complex lifetime systems requiring manual annotations, SRG verifies reference topology directly in the AST lexical scope at compile time.",
      },
      {
        id: "ownership-modifiers",
        title: "The Five Ownership Modifiers",
        level: "h2",
        content: "The Sotlas grammar defines explicit ownership qualifiers:",
        listItems: [
          "sole: Exclusive static ownership. Immediate deterministic destruction the moment it exits scope. Strictly zero runtime overhead.",
          "co-owned: Scoped shared ownership graph (optimized hybrid ARC). Reference cycles are resolved statically via AST topology.",
          "island: Completely isolated memory region for data-race-free concurrent execution.",
          "whisper: Weak graph reference that does not increment retain counters and safely evaluates to nil if targets are freed.",
          "direct: Direct reference without reference counting overhead, providing maximum speed in latency-critical loops.",
        ],
        code: {
          caption: "Practical SRG Ownership Modifiers",
          lines: [
            "// Sole exclusive allocation",
            "let buffer: sole Buffer = Buffer.create(4096);",
            "",
            "// Safe shared ownership graph",
            "let root: co-owned Node = Node.create();",
            "let weak_ref: whisper Node = root;",
            "",
            "// High-performance direct pointer",
            "let fast_ptr: direct Node = root;",
          ],
        },
      },
      {
        id: "handover-quarantine",
        title: "'handover' and 'quarantine' Instructions",
        level: "h3",
        content:
          "Ownership flow is controlled via first-class statements:",
        code: {
          caption: "handover and quarantine",
          lines: [
            "fn transfer_buffer(buf: sole Buffer) -> sole Buffer {",
            "    // 'handover' transfers exclusive ownership without running destructor",
            "    handover buf;",
            "}",
            "",
            "fn isolate_resource(res: sole Resource) -> Void {",
            "    // 'quarantine' packages the resource into an isolated 'island' region",
            "    quarantine res;",
            "}",
          ],
        },
      },
    ],
  },

  pointers: {
    title: "Topology Pointers",
    description: "Architecture-aware typed pointers conscious of machine physical address spaces.",
    breadcrumb: ["Low-Level & Hardware", "Topology Pointers"],
    sections: [
      {
        id: "topology-concept",
        title: "Physiographic Memory Topology",
        level: "h2",
        content:
          "In modern systems programming, not all memory behaves the same. A pointer to a GPU MMIO register does not behave like a CPU bus port or a DMA ring buffer. Sotlas formalizes this physical reality in the type system via Topology Pointers:",
      },
      {
        id: "pointer-types",
        title: "Topology Pointer Classification",
        level: "h2",
        content: "The syntax '*topology Type' expresses exact access semantics:",
        listItems: [
          "*rawphys T: Direct physical address mapping (MMIO controllers, GOP framebuffers, chip registers).",
          "*virtmap T: Pointer within the virtual address space managed by the paged MMU.",
          "*portwire T: Dedicated processor I/O port lines (in/out instructions on x86 architectures).",
          "*dmazone T: Direct Memory Access buffer, with boundary alignment for zero-copy CPU-peripheral transfers.",
          "*voidzero: Untyped opaque pointer (strictly constrained equivalent to C's void*).",
        ],
        code: {
          caption: "Topology Pointers Example",
          lines: [
            "// Physical MMIO video framebuffer mapping",
            "let framebuffer = 0xFD000000 as *rawphys mut UInt32;",
            "*framebuffer = 0xFF00FF; // Draws magenta pixel",
            "",
            "// Keyboard controller status I/O port",
            "let kbd_port = 0x64 as *portwire UInt8;",
            "let kbd_status: UInt8 = *kbd_port;",
            "",
            "// Aligned DMA ring buffer for Ethernet controller",
            "let rx_ring: *dmazone mut PacketBuffer = allocate_dma(4096);",
          ],
        },
      },
      {
        id: "pointer-mutability",
        title: "Mutable and Constant Pointers",
        level: "h3",
        content:
          "The modifiers '*mut T' and '*const T' combine with topologies for precise, safe read and write access control.",
      },
    ],
  },

  hardware: {
    title: "Hardware, Clinch & Trapfn",
    description: "Atomic critical sections, memory persistence barriers, inline assembly, and interrupt service routines.",
    breadcrumb: ["Low-Level & Hardware", "Hardware, Clinch & Trapfn"],
    sections: [
      {
        id: "clinch-revert",
        title: "clinch & revert — Atomic Critical Sections",
        level: "h2",
        content:
          "The 'clinch' block introduces a critical section with hardware-enforced atomic parity (such as disabling and restoring CPU interrupt flags). If an exception or abort occurs, the associated 'revert' block immediately executes state compensation:",
        code: {
          caption: "clinch/revert Critical Section",
          lines: [
            "clinch {",
            "    // Interrupts atomically masked (e.g. CLI on x86)",
            "    update_critical_page_table();",
            "} revert {",
            "    // Executed with absolute guarantee of CPU flags restoration",
            "    restore_cpu_flags();",
            "}",
          ],
        },
      },
      {
        id: "quench",
        title: "quench — Persistent Memory Barriers",
        level: "h2",
        content:
          "The 'quench' block issues a hardware persistence barrier in the memory subsystem (equivalent to clwb + sfence). Indispensable for non-volatile storage and storage-class memory (NVDIMM):",
        code: {
          caption: "quench Barrier",
          lines: [
            "quench {",
            "    nvdimm_log.commit_transaction();",
            "}",
          ],
        },
      },
      {
        id: "trapfn",
        title: "trapfn — Native Interrupt Handlers",
        level: "h2",
        content:
          "Unlike standard functions, 'trapfn' is compiled using the processor's native interrupt ABI (__attribute__((interrupt))), automatically saving and restoring all CPU registers upon entry and exit:",
        code: {
          caption: "ISR Interrupt Handler",
          lines: [
            "pub trapfn irq1_keyboard_handler(frame: *rawphys InterruptFrame) -> Void {",
            "    let port = 0x60 as *portwire UInt8;",
            "    let scancode: UInt8 = *port;",
            "    ring_buffer.append(scancode);",
            "    ack_pic();",
            "}",
          ],
        },
      },
      {
        id: "mesh-layout",
        title: "'mesh' Declarations for Hardware Registers",
        level: "h3",
        content:
          "The 'mesh' declaration defines the exact spatial memory layout of mapped hardware registers with strict byte alignments:",
        code: {
          caption: "mesh Structure",
          lines: [
            "mesh UartRegisters {",
            "    data:     UInt8 align(1);",
            "    int_en:   UInt8 align(1);",
            "    fifo_ctl: UInt8 align(1);",
            "    line_ctl: UInt8 align(1);",
            "}",
          ],
        },
      },
      {
        id: "emit-asm",
        title: "emit — Inline Assembly with Explicit Clobbers",
        level: "h3",
        content:
          "The 'emit' instruction delivers clean inline assembly integrated with register constraints and target architectural rules:",
        code: {
          caption: "emit assembly",
          lines: [
            'emit("hlt");',
            'emit("mov cr3, %0" : : cr3_val : "memory");',
          ],
        },
      },
    ],
  },

  "bit-slicing": {
    title: "Bit-Slicing & Endianness",
    description: "Native field bit-slicing (.slit), isolated bit checking (.notch), and zero-cost endianness reversal (.strand).",
    breadcrumb: ["Low-Level & Hardware", "Bit-Slicing & Endianness"],
    sections: [
      {
        id: "slit",
        title: ".slit[start..end] — Native Bit-Slicing",
        level: "h2",
        content:
          "Say goodbye to manual, error-prone bitwise shift and mask operations. In Sotlas, any integer expression provides the native '.slit[start..end]' operator to extract bit fields with zero runtime overhead:",
        code: {
          caption: "Field Extraction with .slit",
          lines: [
            "let reg: UInt32 = 0xABCD1234;",
            "",
            "// Extracts bits 0 through 7 (first byte)",
            "let byte0 = reg.slit[0..7];",
            "",
            "// Extracts opcode (bits 24 through 31)",
            "let opcode = reg.slit[24..31];",
          ],
        },
      },
      {
        id: "notch",
        title: ".notch[index] — Isolated Bit Extraction",
        level: "h2",
        content:
          "The '.notch[index]' operator directly extracts a single bit value, ideal for checking processor flags and hardware bus status lines:",
        code: {
          caption: "Using .notch",
          lines: [
            "let status: UInt16 = read_bus_status();",
            "let buffer_full: Bool = status.notch[3] == 1;",
            "let parity_error: Bool = status.notch[7] == 1;",
          ],
        },
      },
      {
        id: "strand",
        title: ".strand — Endianness Swapping",
        level: "h3",
        content:
          "The postfix '.strand' method swaps byte order using the processor's native bswap hardware instruction:",
        code: {
          caption: "Endianness Conversion",
          lines: [
            "let le_data: UInt32 = 0x12345678;",
            "let be_data: UInt32 = le_data.strand;",
            "// Result: 0x78563412",
          ],
        },
      },
    ],
  },

  keywords: {
    title: "Keywords Dictionary",
    description: "Complete catalog of Sotlas keywords, hardware primitives, memory qualifiers, and native operators.",
    breadcrumb: ["Specification & Standards", "Keywords Dictionary"],
    sections: [
      {
        id: "sotlas-lexicon",
        title: "Language Lexicon and Real-World Usage",
        level: "h2",
        content:
          "Sotlas defines keywords with strict semantics to eliminate ambiguity between bare-metal silicon and high-level software abstractions. Every keyword plays a direct role in compiler lowering and static verification — proven in production inside Baken OS, where Sotlas controls UEFI bootstrap, GOP framebuffer initialization, ACPI tables, and peripheral drivers.",
      },
      {
        id: "kw-profiles",
        title: "Target Profiles",
        level: "h2",
        content: "Specify compiler constraints and API permissions without changing grammar or modules:",
        listItems: [
          "barecore — Freestanding environment for bootloaders, kernels, and embedded firmware with zero OS dependencies.",
          "native — OS-hosted applications with network I/O, filesystem, and native threading.",
          "web — Sandboxed WebAssembly output for secure browser runtimes.",
        ],
        code: {
          caption: "Profiles",
          lines: [
            "target barecore; // Enables *rawphys, clinch, trapfn",
            "target native;   // Enables OS threads and file I/O",
            "target web;      // Conforms to WebAssembly runtime",
          ],
        },
      },
      {
        id: "kw-srg",
        title: "SRG Memory Graph (Deterministic Management)",
        level: "h2",
        content: "Ownership and lifecycle keywords without a garbage collector:",
        listItems: [
          "sole — Exclusive static ownership with immediate zero-cost deterministic destruction.",
          "co-owned — Shared ownership graph (hybrid ARC) with static cycle resolution in the AST.",
          "island — Completely isolated memory region for concurrent execution without data races.",
          "whisper — Weak reference that does not increment retain counters and safely resolves to nil.",
          "direct — Direct reference offering maximum performance under programmer control.",
          "handover — Atomically moves exclusive sole ownership to caller without invoking destructor.",
          "quarantine — Packages an owned resource into a new isolated 'island' region.",
        ],
        code: {
          caption: "SRG in Action",
          lines: [
            "let packet: sole Packet = Packet.create();",
            "quarantine packet;",
            "handover packet;",
          ],
        },
      },
      {
        id: "kw-topology",
        title: "Topology Pointers (Hardware Pointers)",
        level: "h2",
        content: "Physiographic pointer types conscious of physical machine buses:",
        listItems: [
          "*rawphys — Direct physical address mapping (MMIO, GOP framebuffer, chip registers).",
          "*virtmap — Pointer to virtual address space managed by the paged MMU.",
          "*portwire — Dedicated processor I/O port lines (x86 in/out instructions).",
          "*dmazone — Aligned Direct Memory Access buffer for zero-copy transfers.",
          "*voidzero — Opaque untyped pointer (strictly constrained equivalent to C void*).",
        ],
      },
      {
        id: "kw-hardware",
        title: "Hardware, Critical Sections & Interrupts",
        level: "h2",
        content: "Native instructions for atomic control and hardware synchronization:",
        listItems: [
          "clinch / revert — Critical section with atomic interrupt masking and guaranteed state restoration.",
          "rebound — Explicit restoration of processor execution context.",
          "quench — Hardware persistence barrier and cache flush (sfence + clwb).",
          "gate — Structured runtime assertion with controlled fallback handling without brute crash.",
          "trapfn — Interrupt service routine with native ISR ABI (__attribute__((interrupt))).",
          "mesh — Memory struct with explicit physical bus alignment constraints (align(N)).",
          "emit — Inline assembly with typed architectural clobbers and constraints.",
        ],
      },
      {
        id: "kw-contracts",
        title: "API Contracts and OO without Headers",
        level: "h3",
        content: "Sotlas modular mechanism for verifiable interfaces and inheritance:",
        listItems: [
          "spec — Formal verifiable public API contract (replaces .h and .hpp files).",
          "adopts — Declaration of formal spec adoption and fulfillment by classes and structs.",
          "mould / moldable / reshape — Comptime evaluation, polymorphic methods, and explicit overrides.",
          "capsule / lineage — Access visibility scoped to package or class inheritance lineage.",
          "irqfree — Statically proven lock-free, allocation-free function safe for ISRs.",
        ],
      },
      {
        id: "kw-bits",
        title: "State Qualifiers and Bit Manipulation",
        level: "h3",
        content: "Fine-grained control over registers and variables:",
        listItems: [
          "shielded — Variable protected against concurrency or DMA memory bus interference.",
          "nvkeep — Guaranteed retention in non-volatile memory (NVDIMM/FRAM).",
          "seal — Permanent post-initialization immutability lock.",
          ".slit[start..end] — Native zero-cost bit-slice field extraction.",
          ".notch[index] — Isolated bit extraction for status flags.",
          ".strand — Instant endianness swap using CPU bswap instruction.",
          ".bound[min..max] — Compile-time enforced Bounded Type constraint.",
        ],
      },
    ],
  },

  "vscode-tutorial": {
    title: "VS Code Setup & Tutorial",
    description: "Complete guide to configuring Visual Studio Code for Sotlas development with language servers, syntax highlighting, task automation, and native debugging.",
    breadcrumb: ["Getting Started", "VS Code Setup & Tutorial"],
    sections: [
      {
        id: "extension-installation",
        title: "Installing the Official VS Code Extension",
        level: "h2",
        content:
          "The official Sotlas extension package is bundled directly inside the repository under editors/vscode/sotlas-0.5.1.vsix. You can install it into Visual Studio Code with a single CLI command or through the Extensions panel.",
        code: {
          caption: "Terminal — Installing .vsix package",
          lines: [
            "# Install via VS Code Command Line Interface",
            "code --install-extension editors/vscode/sotlas-0.5.1.vsix",
            "",
            "# Or inside VS Code: Ctrl+Shift+P -> 'Extensions: Install from VSIX...'",
          ],
        },
        listItems: [
          "Full TextMate syntax highlighting for .sotlas and .sot source files.",
          "Automatic bracket matching and register bit-slice notation highlighting.",
          "Code snippet expansions for @system, @export, clinch, and topology pointers.",
          "Integrated file icons and custom theme support.",
        ],
      },
      {
        id: "lsp-configuration",
        title: "Language Server Protocol (LSP) Integration",
        level: "h2",
        content:
          "The Sotlas compiler includes a high-performance built-in Language Server (sotlas lsp). It provides real-time static analysis, error squiggles, type inspection on hover, and semantic code completions without external dependencies.",
        code: {
          caption: "Settings — .vscode/settings.json",
          lines: [
            "{",
            "  \"sotlas.languageServer.enable\": true,",
            "  \"sotlas.languageServer.path\": \"sotlas\",",
            "  \"sotlas.languageServer.arguments\": [\"lsp\"],",
            "  \"sotlas.formatOnSave\": true,",
            "  \"sotlas.diagnostics.srgBorrowChecker\": true",
            "}",
          ],
        },
      },
      {
        id: "build-tasks",
        title: "Build and Test Tasks (tasks.json)",
        level: "h2",
        content:
          "Automate common workflow operations directly within VS Code by configuring build tasks in .vscode/tasks.json. Use Ctrl+Shift+B to compile or verify your codebase with zero friction.",
        code: {
          caption: "Configuration — .vscode/tasks.json",
          lines: [
            "{",
            "  \"version\": \"2.0.0\",",
            "  \"tasks\": [",
            "    {",
            "      \"label\": \"Sotlas: Build Project\",",
            "      \"type\": \"shell\",",
            "      \"command\": \"sotlas\",",
            "      \"args\": [\"build\"],",
            "      \"group\": { \"kind\": \"build\", \"isDefault\": true },",
            "      \"problemMatcher\": [\"$gcc\"]",
            "    },",
            "    {",
            "      \"label\": \"Sotlas: Check Syntax & Types\",",
            "      \"type\": \"shell\",",
            "      \"command\": \"sotlas\",",
            "      \"args\": [\"check\", \"${file}\"],",
            "      \"problemMatcher\": [\"$gcc\"]",
            "    },",
            "    {",
            "      \"label\": \"Sotlas: Run Current File\",",
            "      \"type\": \"shell\",",
            "      \"command\": \"sotlas\",",
            "      \"args\": [\"run\", \"${file}\"]",
            "    }",
            "  ]",
            "}",
          ],
        },
      },
      {
        id: "native-debugging",
        title: "Native Debugging (launch.json)",
        level: "h2",
        content:
          "Because Sotlas compiles directly to native machine code with DWARF debug symbols or emits freestanding C11, you can step through your code with GDB or LLDB using standard VS Code debug extensions (such as CodeLLDB).",
        code: {
          caption: "Configuration — .vscode/launch.json",
          lines: [
            "{",
            "  \"version\": \"0.2.0\",",
            "  \"configurations\": [",
            "    {",
            "      \"name\": \"Debug Sotlas Binary (CodeLLDB)\",",
            "      \"type\": \"lldb\",",
            "      \"request\": \"launch\",",
            "      \"program\": \"${workspaceFolder}/build/bin/my_project\",",
            "      \"args\": [],",
            "      \"cwd\": \"${workspaceFolder}\",",
            "      \"preLaunchTask\": \"Sotlas: Build Project\",",
            "      \"stopOnEntry\": false",
            "    }",
            "  ]",
            "}",
          ],
        },
      },
      {
        id: "tutorial-driver",
        title: "Step-by-Step Tutorial: Writing a Driver in VS Code",
        level: "h2",
        content:
          "Let us walk through building an isolated UART peripheral driver from scratch inside VS Code:",
        listItems: [
          "1. Open terminal (Ctrl+`): Run 'sotlas new uart_driver' to scaffold the project structure.",
          "2. Open 'src/main.sotlas': Notice that syntax highlighting and token classifications are active immediately.",
          "3. Define the physical MMIO register base: '*rawphys u32' mapped to 0x1000_0000.",
          "4. Apply the '@system' modifier to gate I/O memory transactions safely inside an explicit 'unsafe' block.",
          "5. Save the file: The LSP automatically checks types and outputs feedback in the Problems panel.",
          "6. Press Ctrl+Shift+B: The build task invokes 'sotlas build', producing an optimized, freestanding binary.",
        ],
      },
    ],
  },

  community: {
    title: "Community & Contributing",
    description: "How to participate in the RFC process and contribute to the Sotlas language evolution.",
    breadcrumb: ["Specification & Standards", "Community & Contributing"],
    sections: [
      {
        id: "rfc-process",
        title: "Language RFC Process",
        level: "h2",
        content:
          "All additions to the formal grammar or compiler semantics are submitted through the RFC (Request for Comments) process. The technical community debates ABI stability, codegen costs, and developer ergonomics before any change is accepted.",
      },
      {
        id: "contributions",
        title: "How to Contribute",
        level: "h2",
        content: "Active areas open to systems engineers and computer scientists:",
        listItems: [
          "AST scope graph analysis optimizations in SRG.",
          "Code generation backends for emerging targets (RISC-V 64, AArch64 bare-metal, x86_64 UEFI).",
          "Language Server Protocol (LSP) extensions with real-time diagnostics.",
          "Peripheral driver implementations (NVMe, USB/xHCI, Ethernet).",
        ],
      },
    ],
  },

  compiler: {
    title: "SIR SSA & C11 Stage-0 Pipeline",
    description: "Inside the Sotlas compiler: canonical lexing, SSA optimization passes, and the freestanding C11 bootstrap backend.",
    breadcrumb: ["Architecture & Compiler", "SIR SSA & C11 Pipeline"],
    sections: [
      {
        id: "compiler-overview",
        title: "Strict Phased Architecture",
        level: "h2",
        content:
          "The Sotlas compiler is built with strict layered separation of concerns. The pipeline transforms source text into a formal intermediate representation (SIR SSA) before emitting machine code:",
        listItems: [
          "Lexer & Spans: Deterministic tokenization preserving precise source spans for diagnostics.",
          "Canonical EBNF Parser: Recursive-descent parser without grammatical ambiguities.",
          "Sema (Semantic Analysis): Type resolution, static inference, and spec contract validation.",
          "Safety & Effects Engine: Formal isolation between privileged capabilities (@system) and memory manipulation (unsafe).",
          "SIR Gen & Passes: Static Single Assignment (SSA) code generation with Dead Code Elimination (DCE) and ownership verification.",
          "Freestanding C11 Backend: Emits portable ANSI C11 for GCC/Clang with zero libc dependencies, or compiles directly via LLVM.",
        ],
      },
      {
        id: "sir-ssa",
        title: "Sotlas Intermediate Representation (SIR)",
        level: "h2",
        content:
          "SIR is the backbone of the compiler. Structured in Static Single Assignment, it verifies definite initialization of all variables, proves that no raw pointer escapes unsafe blocks, and optimizes ARC retain/release calls in-line.",
        code: {
          caption: "Example — Inspecting SIR with the CLI",
          lines: [
            "# Inspect the intermediate SSA code emitted by the compiler",
            "sotlas dump-sir kernel_main.sotlas",
          ],
        },
      },
      {
        id: "c11-stage0",
        title: "Freestanding C11 Backend (Stage-0 Bootstrap)",
        level: "h2",
        content:
          "To enable universal cross-compilation for any microcontroller or processor without requiring complex pre-installed runtimes, the Sotlas Stage-0 compiler emits pure freestanding C11 code compatible with any standard toolchain (GCC, Clang, MSVC).",
      },
    ],
  },

  interoperability: {
    title: "C & C++ Deep Interoperability",
    description: "Production-grade, zero-overhead bidirectional interoperability with C and modern C++ via embedded Clang modules and deterministic ABI mapping.",
    breadcrumb: ["Architecture & Compiler", "C & C++ Interoperability"],
    sections: [
      {
        id: "interop-overview",
        title: "Direct Clang & C ABI Architecture",
        level: "h2",
        content:
          "Sotlas embeds Clang compilation services to provide direct, bidirectional interoperability with C and C++ codebases without requiring manual FFI wrappers, SWIG layers, or runtime dispatch penalties. C++ APIs are represented as native Sotlas declarations, and Sotlas types compile to direct, inlinable C++ symbols.",
        listItems: [
          "Zero Runtime Cost: Direct assembly-level calling convention (cdecl / SysV / Microsoft x64) without dynamic thunks.",
          "Header & Clang Module Import: Native ingestion of C and C++ headers via module.modulemap.",
          "Safe Boundary Enforcement: Legacy pointers and mutating references are quarantined behind explicit lexical unsafe blocks.",
          "Bidirectional Exposure: Export native Sotlas functions and structures directly to C and C++ with compiler-generated headers.",
        ],
      },
      {
        id: "importing-clang",
        title: "Importing C & C++ Headers via Clang Modules",
        level: "h2",
        content:
          "To consume existing C and C++ libraries, define a module.modulemap inside your include directory. The Sotlas compiler invokes Clang to build a semantic AST model of the library, exposing classes, templates, and free functions directly to your source files.",
        code: {
          caption: "module.modulemap — C++ Library Definition",
          lines: [
            "module ForestEngine {",
            "    header \"Forest.hpp\"",
            "    header \"Tree.hpp\"",
            "    export *",
            "}",
          ],
        },
      },
      {
        id: "calling-cpp-functions",
        title: "Calling C & C++ Functions and Constructors",
        level: "h2",
        content:
          "Imported C++ functions and class constructors are invoked using standard Sotlas syntax. Constant member functions map to nonmutating methods, while non-const member functions map to mutating methods.",
        code: {
          caption: "Example — Using Imported C++ Types",
          lines: [
            "import ForestEngine;",
            "",
            "pub fn spawn_woodland() {",
            "    // Directly calls C++ constructor: Tree(TreeKind::Redwood)",
            "    let tree = Tree(.Redwood);",
            "    ",
            "    // Constant member function becomes nonmutating method",
            "    let height: f32 = tree.get_height();",
            "    ",
            "    // Mutating member function requires mutable binding",
            "    let mut oak = Tree(.Oak);",
            "    oak.grow(12.5);",
            "}",
          ],
        },
      },
      {
        id: "cpp-value-types",
        title: "C++ Structures and Classes as Value Types",
        level: "h2",
        content:
          "By default, Sotlas treats imported C++ structs and classes as value types. Copies invoke the underlying C++ copy constructor, and leaving scope triggers the C++ destructor deterministically.",
        listItems: [
          "Copy & Move Semantics: Types with defined copy constructors are copied automatically upon assignment; movable types use C++ move constructors.",
          "Non-Copyable Types: Structs with deleted copy constructors are imported as ~Copyable, enforcing single ownership (sole).",
          "Conditional Copyability: Template specializations can enforce copyability conditionally depending on their inner parameter types.",
        ],
        code: {
          caption: "C++ Header Annotation — Non-copyable Resource",
          lines: [
            "// C++ header with Sotlas bridging annotation",
            "#include <sotlas/bridging.h>",
            "",
            "struct SOTLAS_NONCOPYABLE FileDescriptor {",
            "    FileDescriptor(const char *path);",
            "    ~FileDescriptor();",
            "};",
          ],
        },
      },
      {
        id: "reference-mapping",
        title: "Mapping C++ Types to Reference Types (ARC & Arenas)",
        level: "h2",
        content:
          "Certain C++ architectures rely on persistent identity rather than value copying. Sotlas provides three reference-mapping annotations for C++ classes:",
        listItems: [
          "Immortal References (@immortal_ref): Used for arena-allocated objects and global singletons whose lifetime spans program execution.",
          "Shared References (@shared_ref): Used for intrusive reference-counted objects. Sotlas bridges its ARC retain/release runtime directly to your C++ increment/decrement functions.",
          "Smart Pointer Bridging (@refcounted_ptr): Transparently bridges C++ smart pointers (such as custom RefCountPtr<T>) to native reference types.",
        ],
        code: {
          caption: "Example — Shared Reference Counted C++ Object",
          lines: [
            "// C++ definition with intrusive retain/release",
            "class SharedBuffer : public RefCounted<SharedBuffer> {",
            "public:",
            "    static SharedBuffer* create(size_t size);",
            "    void retain();",
            "    void release();",
            "} SOTLAS_SHARED_REFERENCE(retainSharedBuffer, releaseSharedBuffer);",
            "",
            "// Consumed in Sotlas with seamless ARC lifecycle:",
            "let buf = SharedBuffer.create(1024);",
            "buf.write_u32(0xCAFEBABE); // Automatically released when buf leaves scope",
          ],
        },
      },
      {
        id: "stl-containers",
        title: "C++ Standard Template Library (STL) Integration",
        level: "h2",
        content:
          "Sotlas provides first-class bridging to the standard C++ library (CxxStdlib). Common STL containers conform to native Sotlas protocols for idiomatic iteration, conversion, and lookup.",
        listItems: [
          "std::string: Converts bidirectionally to Sotlas String via std.string(str) and String(cxx_str).",
          "std::vector<T>: Automatically conforms to RandomAccessCollection, enabling safe for-in iteration, indexing, and conversion to Sotlas Array.",
          "std::optional<T>: Maps to Sotlas Option<T> via Option(fromCxx: value).",
          "std::function<R(Args...)>: Can be constructed directly from Sotlas closures with full lexical captures.",
          "std::unordered_map: Conforms to CxxDictionary, providing safe key lookup using subscript syntax.",
        ],
        code: {
          caption: "Example — Iterating std::vector and Using std::string",
          lines: [
            "import CxxStdlib;",
            "",
            "pub fn process_cxx_data() {",
            "    // Create and use std::string",
            "    let cxx_str: std.string = \"Systems text from C++\";",
            "    let sotlas_str: String = String(cxx_str);",
            "    ",
            "    // Traverse std::vector using native for-in loop",
            "    let numbers: std.vector<u32> = get_sensor_readings();",
            "    for reading in numbers {",
            "        log_reading(reading);",
            "    }",
            "}",
          ],
        },
      },
      {
        id: "view-types-lifetimes",
        title: "Working with C++ References and View Types",
        level: "h2",
        content:
          "In C++, member functions that return raw pointers (& or *) often return pointers into internal object state. To prevent use-after-free bugs, Sotlas marks unannotated reference-returning methods with a safety prefix (__methodUnsafe) and requires explicit borrowing wrappers.",
        code: {
          caption: "Safe Borrowing Wrapper Pattern",
          lines: [
            "// Extending C++ Forest class in Sotlas for safe lifetime access",
            "extension Forest {",
            "    pub borrowing fn root_tree_copy() -> Tree {",
            "        // Safely copies out the dereferenced internal pointer",
            "        unsafe {",
            "            return self.__getRootTreeUnsafe().pointee;",
            "        }",
            "    }",
            "}",
          ],
        },
      },
      {
        id: "exporting-to-cpp",
        title: "Exposing Sotlas APIs to C & C++",
        level: "h2",
        content:
          "Sotlas codebases can be embedded incrementally into legacy C and C++ projects. When compiled with the '--emit-header' flag, the compiler generates a C++ header containing inline wrappers that map Sotlas structs, classes, and functions to native C++ types.",
        code: {
          caption: "Consuming Sotlas from C++20",
          lines: [
            "// Generated header by: sotlas compile --emit-header",
            "#include \"SotlasDriver-CXX.h\"",
            "#include <iostream>",
            "",
            "int main() {",
            "    // Call Sotlas top-level module function directly",
            "    auto packet = SotlasDriver::build_telemetry_packet(1001);",
            "    std::cout << \"Packet Size: \" << packet.get_payload_len() << std::endl;",
            "    return 0;",
            "}",
          ],
        },
      },
    ],
  },

  stdlib: {
    title: "Standard Library (stdlib)",
    description: "The Sotlas standard library implemented in pure Sotlas (Sotlas in Sotlas) with freestanding contracts for systems and firmware.",
    breadcrumb: ["Architecture & Compiler", "Standard Library (stdlib)"],
    sections: [
      {
        id: "core-modules",
        title: "Core Modules (stdlib/core/)",
        level: "h2",
        content: "Pure modules free of mandatory heap allocations, ready for use in kernels and bootloaders:",
        listItems: [
          "core::primitives — Numeric constants, integer type limits, and floating point specifications.",
          "core::option — OptionU32, OptionI32, and OptionPtr for null-safe representation without raw nulls.",
          "core::result — ResultU32, ResultI32 with formal ResultCode enumeration for typed errors.",
          "core::mem — Freestanding buffer initialization and copy routines (zero_memory, copy_memory).",
          "core::arc — Deterministic Automatic Reference Counting primitives (ArcHeader, SharedCounter).",
          "core::slice — Safe memory slices with bounds validation (ByteSlice, MutByteSlice).",
          "core::string — Safe UTF-8 text slices (StringSlice).",
          "core::panic — Deterministic machine halt handler for operating systems.",
        ],
        code: {
          caption: "Example — Using Option and Result from stdlib/core",
          lines: [
            "import core::option::*;",
            "import core::result::*;",
            "",
            "pub fn parse_header(data: *const u8, len: usize) -> ResultU32 {",
            "    if len < 4 {",
            "        return ResultU32::err(ResultCode::InvalidData);",
            "    }",
            "    return ResultU32::ok(0xCAFE);",
            "}",
          ],
        },
      },
      {
        id: "system-modules",
        title: "System Module (stdlib/system/)",
        level: "h2",
        content:
          "The system::intrinsics module provides typed wrappers for hardware processor instructions with @system effect (inb, outb, cli, sti, hlt, lcr3, invlpg), allowing whole kernels to be written without scattered assembly macros.",
      },
      {
        id: "runtime-freestanding",
        title: "Freestanding Runtime (stdlib/runtime/)",
        level: "h2",
        content:
          "The Sotlas freestanding C11 runtime (runtime.h, runtime.c) has zero external libc dependencies, making emitted binaries ready to boot on x86_64, AArch64, or RISC-V targets.",
      },
    ],
  },
};

// Register Portuguese backward compatibility aliases
documentationPages["interoperabilidade"] = documentationPages["interoperability"];
documentationPages["sintaxe"] = documentationPages["syntax"];
documentationPages["tipos"] = documentationPages["types"];
documentationPages["memoria"] = documentationPages["memory"];
documentationPages["ponteiros"] = documentationPages["pointers"];
documentationPages["compilador"] = documentationPages["compiler"];
documentationPages["comunidade"] = documentationPages["community"];
documentationPages["perfis"] = documentationPages["profiles"];
documentationPages["instalacao"] = documentationPages["installation"];
documentationPages["primeiro-programa"] = documentationPages["first-program"];
documentationPages["ferramentas"] = documentationPages["tools"];
documentationPages["palavras-chave"] = documentationPages["keywords"];
documentationPages["funcoes"] = documentationPages["functions"];
documentationPages["concorrencia"] = documentationPages["concurrency"];
documentationPages["garantias"] = documentationPages["guarantees"];

export const SLUG_ALIASES: Record<string, string> = {
  "interoperabilidade": "interoperability",
  "sintaxe": "syntax",
  "tipos": "types",
  "memoria": "memory",
  "ponteiros": "pointers",
  "compilador": "compiler",
  "comunidade": "community",
  "perfis": "profiles",
  "instalacao": "installation",
  "primeiro-programa": "first-program",
  "ferramentas": "tools",
  "palavras-chave": "keywords",
  "funcoes": "functions",
  "concorrencia": "concurrency",
  "garantias": "guarantees",
};

export function getDocPage(slug: string): DocPageContent | undefined {
  const canonical = SLUG_ALIASES[slug] || slug;
  return documentationPages[canonical] || documentationPages[slug];
}

export function generateTableOfContents(slug: string) {
  const page = getDocPage(slug);
  if (!page) return [];
  return page.sections.map((section) => ({
    id: section.id,
    title: section.title,
    level: section.level,
  }));
}
