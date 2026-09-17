import ChatBox from "./ChatBox";
import bgWave from "@/assets/bg-wave.png";
import WaveText from "@/components/ui/wave-text";

const AIAssistant = () => {
  return (
    <section className="py-10 md:py-14">
      {/* Background Wave Image - Full Width */}
      <div className="w-full">
        <img
          src={bgWave}
          alt=""
          className="w-full h-auto mix-blend-screen"
        />
      </div>

      <div className="max-w-6xl mx-auto px-4 md:px-8">
        {/* Section Header */}
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-foreground tracking-tight mb-4">
            <WaveText text="Find answers faster with AI assistant." />
          </h2>
          <p className="text-base md:text-lg text-muted-foreground max-w-2xl mx-auto">
            <WaveText text="A chatbot trained on our docs and articles to help you find answers faster." staggerDelay={0.015} />
          </p>
        </div>

        {/* Chat Box */}
        <ChatBox />
      </div>
    </section>
  );
};

export default AIAssistant;
