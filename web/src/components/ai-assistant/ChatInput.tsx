import { useState } from "react";
import { ArrowUp } from "lucide-react";

const ChatInput = () => {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setInput("");
  };

  return (
    <form onSubmit={handleSubmit} className="border border-border bg-card rounded-xl shadow-xs">
      <div className="flex items-center gap-3 px-4 py-2.5">
        {/* Input */}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about syntax, physical pointers, or SRG..."
          maxLength={500}
          aria-label="Message for the assistant"
          className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none"
        />

        {/* Send Button */}
        <button
          type="submit"
          disabled={!input.trim()}
          aria-label="Send message"
          className="flex items-center justify-center w-8 h-8 rounded-xl bg-primary text-primary-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-opacity shadow-xs"
        >
          <ArrowUp className="w-4 h-4" />
        </button>
      </div>
    </form>
  );
};

export default ChatInput;
