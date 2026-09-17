import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Home, ArrowLeft } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import WaveText from "@/components/ui/wave-text";

const NotFound = () => {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      
      <main className="flex flex-col items-center justify-center flex-1 px-4 pt-16">
        <motion.div 
          className="text-center max-w-md"
          initial={{ opacity: 0, y: 20, filter: "blur(8px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        >
          {/* 404 Number */}
          <h1 className="text-8xl md:text-9xl font-bold text-foreground tracking-tighter mb-4">
            <WaveText text="404" />
          </h1>

          {/* Title */}
          <h2 className="text-2xl md:text-3xl font-semibold text-foreground tracking-tight mb-4">
            <WaveText text="Page not found" staggerDelay={0.02} />
          </h2>

          {/* Description */}
          <p className="text-muted-foreground mb-8 leading-relaxed">
            The page you're looking for doesn't exist or has been moved. 
            Check the URL or head back to the knowledge hub.
          </p>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              to="/"
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground font-medium rounded-xl transition-colors hover:bg-primary/90"
            >
              <Home className="w-4 h-4" />
              Back to Home
            </Link>
            
            <button
              onClick={() => window.history.back()}
              className="inline-flex items-center gap-2 px-6 py-3 border border-border text-muted-foreground font-medium rounded-xl transition-colors hover:bg-secondary hover:text-foreground"
            >
              <ArrowLeft className="w-4 h-4" />
              Go Back
            </button>
          </div>
        </motion.div>
      </main>

      <Footer />
    </div>
  );
};

export default NotFound;
