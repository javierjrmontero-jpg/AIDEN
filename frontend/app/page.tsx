
"use client";

import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMessage: Message = { role: "user", content: input };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    setLoading(true);
    setMessages([...newMessages, { role: "assistant", content: "" }]);

    try {
      const response = await fetch(
        `http://192.168.2.128:8000/api/v1/chat`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ messages: newMessages }),
        }
      );

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ") && line.trim() !== "data: [DONE]") {
            const text = line.slice(6).replace(/\\n/g, "\n");
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                role: "assistant",
                content: updated[updated.length - 1].content + text,
              };
              return updated;
            });
          }
        }
      }
    } catch (error) {
      console.error("Error:", error);
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: "Error al conectar con AIDEN. Intentá de nuevo.",
        };
        return updated;
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatMessage = (content: string) => {
    return content
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/`(.*?)`/g, "<code class='bg-gray-700 px-1 rounded text-emerald-300 text-xs'>$1</code>")
      .replace(/\n/g, "<br/>");
  };

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-gray-800 bg-gray-900">
        <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        <h1 className="text-lg font-semibold tracking-wide">AIDEN</h1>
        <span className="text-xs text-gray-500 ml-auto">
          Artificial Intelligence Driven ENvironment
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-4">
            <div className="text-4xl font-bold text-gray-700">AIDEN</div>
            <p className="text-gray-500 text-sm max-w-md">
              Tu asistente virtual inteligente. Preguntame lo que necesites.
            </p>
            <div className="grid grid-cols-2 gap-3 mt-4 w-full max-w-lg">
              {[
                "¿Qué podés hacer por mí?",
                "Explicame cómo funciona Docker",
                "Ayudame a escribir un email formal",
                "¿Cuáles son las mejores prácticas en Python?"
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  className="text-left px-4 py-3 bg-gray-800 hover:bg-gray-700 rounded-xl text-xs text-gray-400 hover:text-gray-200 transition-colors border border-gray-700"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-full bg-emerald-600 flex items-center justify-center text-xs font-bold mr-2 mt-1 flex-shrink-0">
                A
              </div>
            )}
            <div
              className={`max-w-2xl px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-emerald-600 text-white rounded-br-sm"
                  : "bg-gray-800 text-gray-100 rounded-bl-sm"
              }`}
            >
              {msg.role === "assistant" && msg.content === "" && loading ? (
                <span className="flex gap-1 items-center text-gray-400">
                  <span className="animate-bounce">●</span>
                  <span className="animate-bounce" style={{animationDelay:"0.1s"}}>●</span>
                  <span className="animate-bounce" style={{animationDelay:"0.2s"}}>●</span>
                </span>
              ) : msg.role === "assistant" ? (
                <div
                  dangerouslySetInnerHTML={{ __html: formatMessage(msg.content) }}
                />
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-4 border-t border-gray-800 bg-gray-900">
        <div className="flex gap-3 max-w-4xl mx-auto">
          <textarea
            className="flex-1 bg-gray-800 text-gray-100 rounded-xl px-4 py-3 text-sm resize-none outline-none border border-gray-700 focus:border-emerald-500 transition-colors placeholder-gray-500"
            placeholder="Escribí tu mensaje... (Enter para enviar, Shift+Enter para nueva línea)"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="px-5 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl text-sm font-medium transition-colors"
          >
            {loading ? "..." : "Enviar"}
          </button>
        </div>
        <p className="text-center text-xs text-gray-600 mt-2">
          AIDEN v0.1 · Semana 1 MVP
        </p>
      </div>
    </div>
  );
}
