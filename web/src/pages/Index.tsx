import { Navbar } from "@/components/navbar";
import { SotlasLanding } from "@/components/home";
import { Footer } from "@/components/footer";
import { Seo } from "@/components/Seo";

const Index = () => {
  return (
    <div className="relative min-h-screen bg-background overflow-x-hidden selection:bg-orange-500/20 selection:text-orange-900 dark:selection:text-orange-200">
      <Seo
        title="Sotlas — Systems Language Development Preview"
        description="Try the Sotlas development preview: a canonical compiler frontend, explicit ownership checks, and bounded C11 and LLVM backends."
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
