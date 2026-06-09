"use client";
import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import MarkdownRenderer from "@/components/MarkdownRenderer";

interface AgentStep {
  type: string;
  tool?: string;
  input?: string;
  result?: string;
  message?: string;
  title?: string;
  content?: string;
  format?: string;
}

interface EmailDraft {
  to: string;
  subject: string;
  body: string;
  account_id: string | null;
  account_label: string;
}

export default function Agent() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [task, setTask] = useState("");
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [finalResult, setFinalResult] = useState("");
  const [document, setDocument] = useState<{title: string; content: string; format: string} | null>(null);
  const [emailDraft, setEmailDraft] = useState<EmailDraft | null>(null);
  const [emailSending, setEmailSending] = useState(false);
  const [emailSent, setEmailSent] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = localStorage.getItem("mate_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps]);

  const sendDraft = async () => {
    if (!emailDraft || !token) return;
    setEmailSending(true);
    try {
      const res = await fetch("/api/v1/email/send-confirmed", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          account_id: emailDraft.account_id,
          to: emailDraft.to,
          subject: emailDraft.subject,
          body: emailDraft.body,
        })
      });
      if (res.ok) {
        setEmailSent(true);
        setEmailDraft(null);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setEmailSending(false);
    }
  };

  const runAgent = async () => {
    if (!task.trim() || !token || running) return;
    setRunning(true);
    setSteps([]);
    setFinalResult("");
    setDocument(null);
    setEmailDraft(null);
    setEmailSent(false);
    try {
      const response = await fetch("/api/v1/agent/run", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ task })
      });
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
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "document") {
              setDocument({ title: data.title, content: data.content, format: data.format || "md" });
            } else if (data.type === "complete") {
              setFinalResult(data.message);
            } else if (data.type === "email_draft") {
              setEmailDraft({
                to: data.to,
                subject: data.subject,
                body: data.body,
                account_id: data.account_id,
                account_label: data.account_label,
              });
            } else {
              setSteps(prev => [...prev, data]);
            }
          } catch (e) {}
        }
      }
    } catch (e) {
      console.error(e);
      setSteps(prev => [...prev, { type: "error", message: "Error de conexión" }]);
    } finally {
      setRunning(false);
    }
  };

  const downloadDocument = () => {
    if (!document) return;
    const blob = new Blob([document.content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement("a");
    a.href = url;
    a.download = `${document.title.replace(/\s+/g, "_")}.${document.format}`;
    window.document.body.appendChild(a);
    a.click();
    window.document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const toolIcon: Record<string, string> = {
    web_search: "🌐",
    execute_python: "🐍",
    create_document: "📄",
  };

  const stepColor: Record<string, string> = {
    start: "text-blue-400",
    step: "text-yellow-400",
    result: "text-gray-400",
    complete: "text-emerald-400",
    error: "text-red-400",
    document: "text-emerald-400",
  };

  const suggestions = [
    "Investigá las últimas noticias sobre IA y generame un informe",
    "Calculá los primeros 20 números de Fibonacci y explicá el patrón",
    "Buscá las mejores prácticas de seguridad en Docker y creá un checklist",
    "Investigá qué es Tailscale y generá un resumen ejecutivo",
  ];

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 px-4 py-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <button onClick={() => router.push("/")}
            className="p-2 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </button>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-semibold">MATE</span>
          </div>
          <span className="text-sm text-gray-500 ml-1">Agente Autónomo</span>
          <span className="text-xs text-gray-600 ml-auto">by JJRM</span>
        </div>

        {/* Input de tarea */}
        <div className="bg-gray-900 rounded-2xl p-5 border border-gray-800 mb-4">
          <h3 className="text-sm font-semibold mb-1">Nueva tarea para el agente</h3>
          <p className="text-xs text-gray-500 mb-4">
            Describí una tarea compleja y MATE la ejecutará paso a paso usando búsqueda web, código y generación de documentos.
          </p>
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Ej: Investigá las últimas tendencias en IA y generame un informe completo en Markdown..."
            rows={3}
            disabled={running}
            className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-600 resize-none text-gray-100 mb-3"
          />
          <button
            onClick={runAgent}
            disabled={running || !task.trim()}
            className="w-full flex items-center justify-center gap-2 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl text-sm font-medium transition-colors"
          >
            {running ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Agente ejecutando...
              </>
            ) : (
              <>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="5 3 19 12 5 21 5 3"/>
                </svg>
                Ejecutar tarea
              </>
            )}
          </button>
          {/* Sugerencias */}
          {steps.length === 0 && !running && (
            <div className="grid grid-cols-2 gap-2 mt-3">
              {suggestions.map((s) => (
                <button key={s} onClick={() => setTask(s)}
                  className="text-left px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs text-gray-500 hover:text-gray-300 transition-colors border border-gray-700">
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Log de ejecución */}
        {steps.length > 0 && (
          <div className="bg-gray-900 rounded-2xl border border-gray-800 overflow-hidden mb-4">
            <div className="px-4 py-3 border-b border-gray-800 flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${running ? "bg-yellow-400 animate-pulse" : "bg-emerald-400"}`} />
              <h3 className="text-sm font-semibold">
                {running ? "Ejecutando..." : "Completado"}
              </h3>
              <span className="text-xs text-gray-600 ml-auto">{steps.length} pasos</span>
            </div>
            <div className="p-4 space-y-2 max-h-80 overflow-y-auto font-mono">
              {steps.map((step, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <span className="text-gray-600 flex-shrink-0 mt-0.5">
                    {step.type === "step" ? toolIcon[step.tool || ""] || "⚙️" :
                     step.type === "start" ? "▶" :
                     step.type === "result" ? "└" :
                     step.type === "error" ? "✗" :
                     step.type === "complete" ? "✓" : "•"}
                  </span>
                  <div className={stepColor[step.type] || "text-gray-400"}>
                    {step.type === "step" && (
                      <span>Usando <strong>{step.tool}</strong>: {step.input}</span>
                    )}
                    {step.type === "result" && (
                      <span className="text-gray-500">{step.result}</span>
                    )}
                    {step.type === "start" && <span>{step.message}</span>}
                    {step.type === "error" && <span>Error: {step.message}</span>}
                  </div>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
          </div>
        )}

        {/* Borrador de email — confirmación del usuario */}
        {emailDraft && !emailSent && (
          <div className="bg-gray-900 rounded-2xl border border-blue-800 p-5 mb-4">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-lg">✉️</span>
              <h3 className="text-sm font-semibold text-blue-400">Borrador de email — pendiente de confirmación</h3>
            </div>
            <div className="space-y-2 text-sm mb-4 bg-gray-800 rounded-xl p-4">
              <div className="flex gap-3">
                <span className="text-gray-500 w-16 flex-shrink-0 text-xs uppercase tracking-wide pt-0.5">Desde</span>
                <span className="text-gray-300">{emailDraft.account_label}</span>
              </div>
              <div className="flex gap-3">
                <span className="text-gray-500 w-16 flex-shrink-0 text-xs uppercase tracking-wide pt-0.5">Para</span>
                <span className="text-gray-300">{emailDraft.to}</span>
              </div>
              <div className="flex gap-3">
                <span className="text-gray-500 w-16 flex-shrink-0 text-xs uppercase tracking-wide pt-0.5">Asunto</span>
                <span className="text-gray-200 font-medium">{emailDraft.subject}</span>
              </div>
              <div className="flex gap-3">
                <span className="text-gray-500 w-16 flex-shrink-0 text-xs uppercase tracking-wide pt-0.5">Cuerpo</span>
                <span className="text-gray-400 whitespace-pre-wrap text-xs leading-relaxed">{emailDraft.body}</span>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={sendDraft}
                disabled={emailSending}
                className="flex-1 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl text-sm font-medium transition-colors"
              >
                {emailSending ? "Enviando..." : "✓ Confirmar envío"}
              </button>
              <button
                onClick={() => setEmailDraft(null)}
                disabled={emailSending}
                className="px-4 py-2.5 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-xl text-sm transition-colors"
              >
                Descartar
              </button>
            </div>
          </div>
        )}

        {/* Confirmación de email enviado */}
        {emailSent && (
          <div className="bg-gray-900 rounded-2xl border border-emerald-800 p-4 mb-4 flex items-center gap-2">
            <span className="text-emerald-400">✅</span>
            <span className="text-sm text-emerald-400">Email enviado correctamente.</span>
          </div>
        )}

        {/* Resultado final */}
        {finalResult && (
          <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5 mb-4">
            <h3 className="text-sm font-semibold mb-3 text-emerald-400">✓ Resultado</h3>
            <MarkdownRenderer content={finalResult} />
          </div>
        )}

        {/* Documento generado */}
        {document && (
          <div className="bg-gray-900 rounded-2xl border border-emerald-800 p-5">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-emerald-400">📄 Documento generado</h3>
                <p className="text-xs text-gray-500">{document.title}</p>
              </div>
              <button onClick={downloadDocument}
                className="flex items-center gap-2 px-3 py-2 bg-emerald-700 hover:bg-emerald-600 rounded-lg text-xs transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="7 10 12 15 17 10"/>
                  <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                Descargar .{document.format}
              </button>
            </div>
            <div className="bg-gray-800 rounded-xl p-4 max-h-64 overflow-y-auto">
              <MarkdownRenderer content={document.content} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
