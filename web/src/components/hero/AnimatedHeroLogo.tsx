import { motion } from "framer-motion";

export function AnimatedHeroLogo() {
  return (
    <motion.div
      initial={{ scale: 0.85, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
      className="relative flex h-12 w-12 items-center justify-center rounded-xl border border-primary/20 bg-card shadow-sm"
    >
      <div className="absolute inset-0 rounded-xl bg-primary/10" />
      <img src="/icone-sotlas.svg" alt="" className="relative h-9 w-9 object-contain" draggable={false} />
    </motion.div>
  );
}

export default AnimatedHeroLogo;
