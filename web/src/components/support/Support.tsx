import { motion } from "framer-motion";
import { MessageSquare, Headset } from "lucide-react";
import SupportCard from "./SupportCard";
import WaveText from "@/components/ui/wave-text";

const supportOptions = [
  {
    icon: MessageSquare,
    title: "Join the Community",
    description: "Discuss RFCs, share feedback, and help evolve the language.",
    linkText: "How to contribute",
    href: "/docs/community",
  },
  {
    icon: Headset,
    title: "Need help?",
    description: "Explore the official documentation and step-by-step setup guides.",
    linkText: "View installation",
    href: "/docs/installation",
  },
];

const Support = () => {
  return (
    <section className="py-10 md:py-14 px-4 md:px-8">
      <div className="max-w-6xl mx-auto">
        {/* Card Container with Luminous Ambient Background */}
        <div className="relative rounded-[2rem] border border-border overflow-hidden p-6 md:p-10 bg-gradient-to-br from-card via-card to-orange-500/5 dark:to-orange-500/10 shadow-sm">
          {/* Subtle Ambient Glow (zero blur) */}
          <div className="absolute top-0 right-0 w-80 h-80 bg-[radial-gradient(circle_at_center,rgba(249,115,22,0.08)_0%,transparent_70%)] pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-80 h-80 bg-[radial-gradient(circle_at_center,rgba(59,130,246,0.05)_0%,transparent_70%)] pointer-events-none" />

          <div className="relative z-10">
            {/* Section Heading */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-8">
              <h2 className="text-2xl md:text-3xl font-bold text-foreground">
                <WaveText text="Community & Support" />
              </h2>
              <div className="flex md:hidden items-center gap-2 text-xs text-muted-foreground font-mono px-3.5 py-1 rounded-full bg-card border border-border w-fit">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                <span>Swipe</span>
                <span className="text-zinc-500 font-sans">⟷</span>
              </div>
            </div>

          {/* Cards Grid / Lateral Scroll on Mobile */}
          <motion.div 
            className="flex overflow-x-auto pb-4 pt-1 snap-x snap-mandatory scrollbar-none overscroll-x-contain -mx-2 px-2 md:mx-0 md:px-0 md:grid md:grid-cols-2 gap-4 md:gap-6 md:overflow-visible md:pb-0"
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
            {supportOptions.map((option) => (
              <motion.div
                key={option.title}
                className="w-[84vw] max-w-[340px] shrink-0 snap-center md:w-auto md:max-w-none md:shrink flex flex-col"
                variants={{
                  hidden: { opacity: 0, y: 20 },
                  visible: { 
                    opacity: 1, 
                    y: 0, 
                    transition: { duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }
                  },
                }}
              >
                <SupportCard
                  icon={option.icon}
                  title={option.title}
                  description={option.description}
                  linkText={option.linkText}
                  href={option.href}
                />
              </motion.div>
            ))}
          </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Support;
