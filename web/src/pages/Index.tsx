import { Navbar } from "@/components/navbar";
import { SotlasLanding } from "@/components/home";
import { Footer } from "@/components/footer";
import { Seo } from "@/components/Seo";

const Index = () => {
  return (
    <div className="relative min-h-screen bg-background overflow-x-hidden selection:bg-orange-500/20 selection:text-orange-900 dark:selection:text-orange-200">
      <Seo
        title="Sotlas — Modern expressiveness with total hardware control"
        description="Compiled systems programming language unifying rich typing, deterministic Scoped Reference Graph (SRG) memory management, and native silicon support."
        path="/"
      />
      <div className="relative z-10">
        <Navbar />
        <main>
          <SotlasLanding />
        </main>
        <Footer />
      </div>
    </div>
  );
};

export default Index;
