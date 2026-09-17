import {
  FileText,
  Download,
  Terminal,
  Wrench,
  Braces,
  Type,
  FunctionSquare,
  Cpu,
  Layers,
  Zap,
  Boxes,
  Users,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  id: string;
  title: string;
  href: string;
  icon: LucideIcon;
  isNew?: boolean;
}

export interface NavGroup {
  id: string;
  title: string;
  items: NavItem[];
}

export interface TableOfContentsItem {
  id: string;
  title: string;
  level: "h2" | "h3";
}

export const navigationGroups: NavGroup[] = [
  {
    id: "getting-started",
    title: "Getting Started",
    items: [
      { id: "overview", title: "Overview", href: "/docs/overview", icon: FileText },
      { id: "guarantees", title: "Guarantees & Lowering", href: "/docs/guarantees", icon: ShieldCheck, isNew: true },
      { id: "profiles", title: "Target Profiles", href: "/docs/profiles", icon: Layers, isNew: true },
      { id: "installation", title: "Installation", href: "/docs/installation", icon: Download },
      { id: "vscode-tutorial", title: "VS Code Setup & Tutorial", href: "/docs/vscode-tutorial", icon: Wrench, isNew: true },
      { id: "first-program", title: "First Program", href: "/docs/first-program", icon: Terminal },
      { id: "tools", title: "Tools & CLI", href: "/docs/tools", icon: Wrench },
    ],
  },
  {
    id: "language",
    title: "Language",
    items: [
      { id: "syntax", title: "Syntax & Declarations", href: "/docs/syntax", icon: Braces },
      { id: "types", title: "Types & Bounded Types", href: "/docs/types", icon: Type },
      { id: "specs-classes", title: "Specs, Structs & Classes", href: "/docs/specs-classes", icon: Boxes, isNew: true },
      { id: "functions", title: "Functions & Modules", href: "/docs/functions", icon: FunctionSquare },
      { id: "concurrency", title: "Concurrency & Islands", href: "/docs/concurrency", icon: Zap },
    ],
  },
  {
    id: "low-level",
    title: "Low-Level & Hardware",
    items: [
      { id: "memory", title: "SRG Memory Graph", href: "/docs/memory", icon: Layers },
      { id: "pointers", title: "Topology Pointers", href: "/docs/pointers", icon: Cpu },
      { id: "hardware", title: "Hardware, Clinch & Trapfn", href: "/docs/hardware", icon: Cpu, isNew: true },
      { id: "bit-slicing", title: "Bit-Slicing & Endianness", href: "/docs/bit-slicing", icon: Terminal, isNew: true },
    ],
  },
  {
    id: "architecture",
    title: "Architecture & Compiler",
    items: [
      { id: "compiler", title: "SIR SSA & C11 Pipeline", href: "/docs/compiler", icon: Cpu, isNew: true },
      { id: "interoperability", title: "C & C++ Interoperability", href: "/docs/interoperability", icon: ShieldCheck, isNew: true },
      { id: "stdlib", title: "Standard Library (stdlib)", href: "/docs/stdlib", icon: Boxes, isNew: true },
    ],
  },
  {
    id: "ecosystem",
    title: "Specification & Standards",
    items: [
      { id: "keywords", title: "Keywords Dictionary", href: "/docs/keywords", icon: Braces, isNew: true },
      { id: "community", title: "Community & Contributing", href: "/docs/community", icon: Users },
    ],
  },
];

export const tableOfContents: TableOfContentsItem[] = [
  { id: "what-is-sotlas", title: "What is Sotlas", level: "h2" },
  { id: "pillars", title: "The Three Core Pillars", level: "h2" },
  { id: "specs-without-headers", title: "Headerless Verifiable Contracts", level: "h3" },
  { id: "next-steps", title: "Next Steps", level: "h2" },
];

export const documentationContent = {
  title: "Overview",
  description: "Discover the Sotlas programming language, its core principles, and what you can build with it.",
  breadcrumb: ["Getting Started", "Overview"],
};
