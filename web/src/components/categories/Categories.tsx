import { motion } from "framer-motion";
import CategoryCard, { CategoryCardData } from "./CategoryCard";
import WaveText from "@/components/ui/wave-text";

const categories: CategoryCardData[] = [
  {
    type: "docs",
    badge: "SRG Engine",
    title: "Documentation",
    description: "Language guides, barecore/native profiles, deterministic SRG memory model, and hardware control.",
    linkText: "Read the guides",
    href: "/docs/overview",
  },
  {
    type: "interop",
    badge: "Zero-Cost ABI",
    title: "C & C++ Interoperability",
    description: "Deep bidirectional interop with C and modern C++, Clang module ingestion, and deterministic ARC bridging.",
    linkText: "Read interop guide",
    href: "/docs/interoperability",
  },
  {
    type: "changelog",
    badge: "v0.5.1 Official",
    title: "News & Releases",
    description: "Track all updates across the language specification and the official Sotlas compiler.",
    linkText: "View releases",
    href: "/changelog",
  },
];

const Categories = () => {
  return (
    <section className="px-4 md:px-8 py-10 md:py-14">
      <div className="max-w-6xl mx-auto">
        {/* Section Heading */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-8 md:mb-10">
          <h2 className="text-2xl md:text-3xl font-bold text-foreground">
            <WaveText text="Explore the language" />
          </h2>
          <div className="flex md:hidden items-center gap-2 text-xs text-muted-foreground font-mono px-3.5 py-1 rounded-full bg-card border border-border w-fit">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse" />
            <span>Swipe to view sections</span>
            <span className="text-zinc-500 font-sans">⟷</span>
          </div>
        </div>

        {/* Cards Grid / Lateral Scroll on Mobile */}
        <motion.div 
          className="flex overflow-x-auto pb-4 pt-1 snap-x snap-mandatory scrollbar-none overscroll-x-contain -mx-4 px-4 sm:-mx-6 sm:px-6 md:mx-0 md:px-0 md:grid md:grid-cols-2 lg:grid-cols-3 gap-6 md:overflow-visible md:pb-0"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.1 }}
          variants={{
            hidden: {},
            visible: {
              transition: {
                staggerChildren: 0.15,
              },
            },
          }}
        >
          {categories.map((category) => (
            <motion.div
              key={category.title}
              className="w-[84vw] max-w-[340px] sm:max-w-[380px] shrink-0 snap-center md:w-auto md:max-w-none md:shrink flex flex-col"
              variants={{
                hidden: { opacity: 0, y: 20 },
                visible: { 
                  opacity: 1, 
                  y: 0, 
                  transition: { duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }
                },
              }}
            >
              <CategoryCard
                type={category.type}
                badge={category.badge}
                title={category.title}
                description={category.description}
                linkText={category.linkText}
                href={category.href}
              />
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
};

export default Categories;
