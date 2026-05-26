"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import MessageActions from "@/components/MessageActions";
import Notification from "@/components/Notification";
import { useNotifications } from "@/components/useNotifications";
import VoiceInput from "@/components/VoiceInput";
import { useTTS } from "@/components/useTTS";

const API_URL = "";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
}

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<{name: string; email: string; is_admin?: boolean} | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Conversation[]>([]);
  const [searchingConv, setSearchingConv] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { notifications, notify, dismiss } = useNotifications();
  const [ttsEnabled, setTtsEnabled] = useState(false);
  const [voiceLang, setVoiceLang] = useState("es-AR");
  const { speak, stop } = useTTS(voiceLang);

useEffect(() => {
  const t = localStorage.getItem("mate_token");
  const u = localStorage.getItem("mate_user");
  if (!t || !u) { router.push("/login"); return; }
  setToken(t);
  const userData = JSON.parse(u);
  setUser(userData);

  fetch("/api/v1/auth/profile", {
  headers: { "Authorization": `Bearer ${t}` }
})
  .then(r => r.json())
  .then(data => {
    setUser({ ...userData, is_admin: data.is_admin });
    const langMap: Record<string, string> = {
      es: "es-AR", en: "en-US", pt: "pt-BR",
      fr: "fr-FR", de: "de-DE", it: "it-IT"
    };
    setVoiceLang(langMap[data.language || "es"] || "es-AR");
  })
  .catch(() => {});
}, [router]);

  const logout = () => {
    localStorage.removeItem("mate_token");
    localStorage.removeItem("mate_user");
    router.push("/login");
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, searching]);

  const authHeaders = useCallback(() => ({
    "Content-Type": "application/json",
    "Authorization": `Bearer ${token}`
  }), [token]);

  const loadConversations = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_URL}/api/v1/conversations`, { headers: authHeaders() });
      if (res.status === 401) { logout(); return; }
      setConversations(await res.json());
    } catch (e) { console.error(e); }
  }, [token, authHeaders]);

  useEffect(() => {
    if (token) loadConversations();
  }, [token, loadConversations]);

  // Verificar crédito Brave
  useEffect(() => {
    if (!token) return;
    fetch("/api/v1/admin/search-usage", {
      headers: { "Authorization": `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        if (data.free_tier_percentage <= 20 && data.searches_this_month > 0) {
          notify(
            `Crédito Brave Search bajo: ${data.free_tier_remaining} búsquedas restantes (${data.free_tier_percentage}%)`,
            "warning"
          );
        }
      })
      .catch(() => {});
  }, [token]);

// Verificar tareas vencidas o por vencer
useEffect(() => {
  if (!token) return;

  const checkTasks = async () => {
    try {
      const res = await fetch("/api/v1/tasks?completed=false", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      const tasks = await res.json();
      const now = new Date();

      tasks.forEach((task: any) => {
        if (!task.due_date) return;
        const due = new Date(task.due_date);
        const diffMs = due.getTime() - now.getTime();
        const diffMins = diffMs / (1000 * 60);

        if (diffMs < 0) {
          // Vencida
          notify(`⏰ Tarea vencida: "${task.title}"`, "error");
        } else if (diffMins <= 30) {
          // Por vencer en 30 minutos
          notify(`⚠️ Tarea por vencer: "${task.title}" (${Math.round(diffMins)} min)`, "warning");
        }
      });
    } catch (e) {
      console.error(e);
    }
  };

  // Verificar al cargar y cada 5 minutos
  checkTasks();
  const interval = setInterval(checkTasks, 5 * 60 * 1000);
  return () => clearInterval(interval);
}, [token]);

  const searchConversations = useCallback(async (query: string) => {
    if (!token || query.length < 2) {
      setSearchResults([]);
      return;
    }
    setSearchingConv(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/conversations/search?q=${encodeURIComponent(query)}`, {
        headers: authHeaders()
      });
      setSearchResults(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setSearchingConv(false);
    }
  }, [token, authHeaders]);

  const loadConversation = async (id: string) => {
    if (!token) return;
    try {
      const res = await fetch(`${API_URL}/api/v1/conversations/${id}/messages`, { headers: authHeaders() });
      const data = await res.json();
      setMessages(data.map((m: any) => ({ role: m.role, content: m.content })));
      setConversationId(id);
    } catch (e) { console.error(e); }
  };

  const newConversation = () => { setMessages([]); setConversationId(null); };

  const deleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await fetch(`${API_URL}/api/v1/conversations/${id}`, { method: "DELETE", headers: authHeaders() });
    if (conversationId === id) newConversation();
    loadConversations();
  };

  const exportConversation = async (id: string, format: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!token) return;
    try {
      const res = await fetch(`${API_URL}/api/v1/conversations/${id}/export/${format}`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `mate_conversacion.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) { console.error(e); }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading || !token) return;
    const userMessage: Message = { role: "user", content: input };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    setLoading(true);
    setSearching(false);
    setMessages([...newMessages, { role: "assistant", content: "" }]);

    try {
      const response = await fetch(`${API_URL}/api/v1/chat`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ messages: newMessages, conversation_id: conversationId }),
      });
      if (response.status === 401) { logout(); return; }

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
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6).trim();
          if (payload === "[DONE]") continue;

          let text: string;
          try { text = JSON.parse(payload); } catch { text = payload; }

          if (payload.startsWith("[CONV:")) {
            setConversationId(payload.slice(6, -1));
            loadConversations();
            continue;
          }
          if (text === "[STATUS:searching]") { setSearching(true); continue; }
          if (text === "[STATUS:done]") { setSearching(false); continue; }

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
    } catch (error) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: "assistant", content: "Error al conectar con MATE." };
        return updated;
      });
      // Leer respuesta en voz alta si TTS está activado
if (ttsEnabled) {
  setMessages(prev => {
    const last = prev[prev.length - 1];
    if (last?.role === "assistant" && last.content) {
      speak(last.content);
    }
    return prev;
  });
}
    } finally {
      setLoading(false);
      setSearching(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("es-AR", { day: "2-digit", month: "short" });

  if (!user) return null;

  const displayedConversations = searchQuery.length >= 2 ? searchResults : conversations;

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
      {sidebarOpen && (
       <div className="w-64 flex flex-col border-r border-gray-800 bg-gray-900 overflow-hidden">
          {/* Header sidebar */}
          <div className="px-4 py-4 border-b border-gray-800">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="font-semibold text-sm">MATE</span>
            </div>
            <button onClick={newConversation}
              className="w-full px-3 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-xs font-medium transition-colors mb-2">
              + Nueva conversación
            </button>
            {/* Buscador */}
            <div className="relative">
              <input
                type="text"
                placeholder="Buscar conversaciones..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  searchConversations(e.target.value);
                }}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs outline-none focus:border-emerald-500 transition-colors placeholder-gray-600 text-gray-300"
              />
              {searchQuery && (
                <button
                  onClick={() => { setSearchQuery(""); setSearchResults([]); }}
                  className="absolute right-2 top-2 text-gray-500 hover:text-gray-300"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              )}
            </div>
          </div>

          {/* Lista de conversaciones */}
          <div className="flex-1 overflow-y-auto overflow-x-hidden py-2">
            {searchQuery.length >= 2 && searchResults.length === 0 && !searchingConv && (
              <p className="text-xs text-gray-600 text-center mt-4 px-4">Sin resultados</p>
            )}
            {searchQuery.length < 2 && conversations.length === 0 && (
              <p className="text-xs text-gray-600 text-center mt-4 px-4">No hay conversaciones aún</p>
            )}
            {displayedConversations.map((conv) => (
              <div key={conv.id} onClick={() => loadConversation(conv.id)}
                className={`group flex items-center gap-2 px-3 py-2 mx-2 rounded-lg cursor-pointer transition-colors ${
                  conversationId === conv.id ? "bg-gray-700" : "hover:bg-gray-800"
                }`}>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-300 truncate">{conv.title}</p>
                  <p className="text-xs text-gray-600">{formatDate(conv.updated_at)}</p>
                </div>
                <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-all">
                  <button onClick={(e) => exportConversation(conv.id, "md", e)} title="Exportar"
                    className="p-1 rounded hover:bg-emerald-800 text-gray-500 hover:text-emerald-300 transition-colors">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                      <polyline points="7 10 12 15 17 10"/>
                      <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                  </button>
                  <button onClick={(e) => deleteConversation(conv.id, e)} title="Eliminar"
                    className="p-1 rounded hover:bg-red-900 text-gray-500 hover:text-red-400 transition-colors">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6"/>
                      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                      <path d="M10 11v6M14 11v6"/>
                      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Footer sidebar */}
          <div className="px-4 py-3 border-t border-gray-800 space-y-1">
            <button onClick={() => router.push("/profile")}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-800 transition-colors text-left">
              <div className="w-6 h-6 rounded-full bg-emerald-700 flex items-center justify-center text-xs font-bold flex-shrink-0">
                {user.name[0].toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-gray-300 truncate">{user.name}</p>
                <p className="text-xs text-gray-600 truncate">{user.email}</p>
              </div>
            </button>
          <div className="grid grid-cols-4 gap-1">
            <button onClick={() => router.push("/profile")}
              className="flex flex-col items-center gap-1 px-2 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors">
              <span className="text-sm">👤</span>
              <span className="text-xs text-gray-500">Perfil</span>
            </button>
            <button onClick={() => router.push("/documents")}
              className="flex flex-col items-center gap-1 px-2 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors">
              <span className="text-sm">📄</span>
              <span className="text-xs text-gray-500">Docs</span>
            </button>
            <button onClick={() => router.push("/memories")}
              className="flex flex-col items-center gap-1 px-2 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors">
              <span className="text-sm">🧠</span>
              <span className="text-xs text-gray-500">Memoria</span>
            </button>
            <button onClick={() => router.push("/tasks")}
              className="flex flex-col items-center gap-1 px-2 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors">
              <span className="text-sm">✅</span>
              <span className="text-xs text-gray-500">Tareas</span>
            </button>
          </div>
          <button onClick={() => router.push("/email")}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors">
            <span className="text-sm">📧</span>
            <span className="text-xs text-gray-400">Email</span>
          </button>
          <button onClick={() => router.push("/stats")}
  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors">
  <span className="text-sm">📊</span>
  <span className="text-xs text-gray-400">Estadísticas</span>
</button>
                    {user?.is_admin && (
                      
            <button onClick={() => router.push("/admin")}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800 hover:bg-emerald-900 transition-colors">
              <span className="text-sm">⚙️</span>
              <span className="text-xs text-gray-400">Administración</span>
            </button>
          )}
            <button onClick={logout}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-red-900/30 transition-colors">
              <span className="text-sm">🚪</span>
              <span className="text-xs text-gray-500">Salir</span>
            </button>
          </div>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 flex flex-col">
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-800 bg-gray-900">
          <button onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-gray-500 hover:text-gray-300 transition-colors text-lg">☰</button>
          <span className="text-sm font-medium">
            {conversationId
              ? conversations.find((c) => c.id === conversationId)?.title || "Conversación"
              : "Nueva conversación"}
          </span>
          <div className="flex items-center gap-3 ml-auto">
            <span className="text-xs text-gray-500">Motor de Asistencia Técnica e Inteligencia by JJRM</span>
            <span className="text-xs text-emerald-400 font-medium">{user.name}</span>
            <button onClick={logout} className="text-xs text-gray-500 hover:text-red-400 transition-colors">Salir</button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto overflow-x-hidden px-4 py-6 space-y-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center gap-4">
              <div className="text-4xl font-bold text-gray-700">MATE</div>
              <p className="text-gray-500 text-sm max-w-md">
                Hola {user.name.split(" ")[0]}, ¿en qué puedo ayudarte hoy?
              </p>
              <div className="grid grid-cols-2 gap-3 mt-4 w-full max-w-lg">
                {[
                  "¿Qué podés hacer por mí?",
                  "Últimas noticias sobre IA hoy",
                  "Ayudame a escribir un email formal",
                  "¿Cuáles son las mejores prácticas en Python?",
                ].map((suggestion) => (
                  <button key={suggestion} onClick={() => setInput(suggestion)}
                    className="text-left px-4 py-3 bg-gray-800 hover:bg-gray-700 rounded-xl text-xs text-gray-400 hover:text-gray-200 transition-colors border border-gray-700">
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "assistant" && (
                <div className="w-7 h-7 rounded-full bg-emerald-600 flex items-center justify-center text-xs font-bold mr-2 mt-1 flex-shrink-0">
                  M
                </div>
              )}
              <div className={`group max-w-2xl px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-emerald-600 text-white rounded-br-sm"
                  : "bg-gray-800 text-gray-100 rounded-bl-sm"
              }`}>
                {msg.role === "assistant" && msg.content === "" && loading ? (
                  <span className="flex gap-1 items-center text-gray-400">
                    <span className="animate-bounce">●</span>
                    <span className="animate-bounce" style={{ animationDelay: "0.1s" }}>●</span>
                    <span className="animate-bounce" style={{ animationDelay: "0.2s" }}>●</span>
                  </span>
                ) : msg.role === "assistant" ? (
                  <div className="w-full">
                    <MarkdownRenderer content={msg.content} token={token ?? undefined} />
                    {msg.content && token && <MessageActions content={msg.content} token={token} />}
                  </div>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}

          {searching && (
            <div className="flex justify-start">
              <div className="w-7 h-7 rounded-full bg-emerald-600 flex items-center justify-center text-xs font-bold mr-2 mt-1 flex-shrink-0">M</div>
              <div className="bg-gray-800 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2">
                <div className="w-3 h-3 rounded-full border-2 border-emerald-400 border-t-transparent animate-spin" />
                <span className="text-xs text-gray-400">Buscando en la web...</span>
                <span className="text-xs">🌐</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

       <div className="px-4 py-4 border-t border-gray-800 bg-gray-900">
          <div className="flex gap-2 max-w-4xl mx-auto items-end">
            <textarea
              className="flex-1 bg-gray-800 text-gray-100 rounded-xl px-4 py-3 text-sm resize-none outline-none border border-gray-700 focus:border-emerald-500 transition-colors placeholder-gray-500 min-w-0"
              placeholder="Escribí tu mensaje... (Enter para enviar, Shift+Enter para nueva línea)"
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <VoiceInput
              onTranscript={(text) => setInput(prev => prev + text)}
              disabled={loading}
              language={voiceLang}
            />
            <button
              onClick={() => { setTtsEnabled(!ttsEnabled); if (ttsEnabled) stop(); }}
              title={ttsEnabled ? "Desactivar voz de MATE" : "Activar voz de MATE"}
              className={`p-3 rounded-xl transition-colors flex-shrink-0 ${
                ttsEnabled ? "bg-emerald-700 hover:bg-emerald-600" : "bg-gray-700 hover:bg-gray-600"
              }`}
            >
              {ttsEnabled ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                  <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
                  <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                  <line x1="23" y1="9" x2="17" y2="15"/>
                  <line x1="17" y1="9" x2="23" y2="15"/>
                </svg>
              )}
            </button>
            <button onClick={sendMessage} disabled={loading || !input.trim()}
              className="px-5 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl text-sm font-medium transition-colors flex-shrink-0">
              {loading ? "..." : "Enviar"}
            </button>
          </div>
          <p className="text-center text-xs text-gray-600 mt-2">
            MATE · Motor de Asistencia Técnica e Inteligencia by JJRM
          </p>
        </div>
      </div>

      {/* Notificaciones */}
      {notifications.map(n => (
        <Notification
          key={n.id}
          message={n.message}
          type={n.type}
          onClose={() => dismiss(n.id)}
        />
      ))}
    </div>
  );
}