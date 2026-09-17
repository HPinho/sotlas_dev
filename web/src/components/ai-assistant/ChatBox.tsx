import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import supportBg from "@/assets/support-bg.png";

const ChatBox = () => {
  return (
    <div 
      className="flex flex-col w-full max-w-2xl mx-auto rounded-3xl border border-border overflow-hidden"
      style={{
        backgroundImage: `url(${supportBg})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      {/* Messages Area */}
      <div className="flex flex-col gap-4 p-6 min-h-[300px] max-h-[400px] overflow-y-auto">
        <ChatMessage role="assistant" content="What can I help you with?" />
        <ChatMessage
          role="assistant"
          content="Demo preview — this chat is not connected to a backend yet. Enable Lovable Cloud to wire it up to a real AI assistant."
        />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-border">
        <ChatInput />
      </div>
    </div>
  );
};

export default ChatBox;
