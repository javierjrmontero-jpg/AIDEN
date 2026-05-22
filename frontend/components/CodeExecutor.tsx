"use client";

import { useState } from "react";

interface Props {
  code: string;
  language: string;
  token: string;
}

const SUPPORTED_LANGUAGES = ["python", "javascript", "bash"];

const LANGUAGE_LABELS: Record<string, string> = {
  python: "▶ Ejecutar Python",
  javascript: "▶ Ejecutar JavaScript",
  bash: "▶ Ejecutar Bash",
};

const LANGUAGE_COLORS: Record<string, string> = {
  python: "bg-blue-700 hover:bg-blue-600",
  javascript: "bg-yellow-700 hover:bg-yellow-600",
  bash: "bg-gray-700 hover:bg-gray-600",
};

export default function CodeExecutor({ code, language, token }: Props) {
  const [result, setResult] = useState<{
    success: boolean;
    output: string;
    error: string;
  } | null>(null);
  const [running, setRunning] = useState(false);

  const lang = language.toLowerCase();
  if (!SUPPORTED_LANGUAGES.includes(lang)) return null;

  const execute = async () => {
    setRunning(true);
    setResult(null);
    try {
      const res = await fetch(`/api/v1/sandbox/execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ code, language: lang })
      });
      const data = await res.json();
      if (!res.ok) {
        setResult({ success: false, output: "", error: data.detail || "Error" });
      } else {
        setResult(data);
      }
    } catch (e) {
      setResult({ success: false, output: "", error: "Error de conexión" });
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="mt-2">
      <button
        onClick={execute}
        disabled={running}
        className={`flex items-center gap-2 px-3 py-1.5 ${LANGUAGE_COLORS[lang]} disabled:bg-gray-700 text-white rounded-lg text-xs font-medium transition-colors`}
      >
        {running ? (
          <>
            <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Ejecutando...
          </>
        ) : (
          LANGUAGE_LABELS[lang]
        )}
      </button>

      {result && (
        <div className={`mt-2 rounded-xl p-3 text-xs font-mono border ${
          result.success
            ? "bg-gray-900 border-emerald-800"
            : "bg-gray-900 border-red-800"
        }`}>
          <div className="flex items-center gap-2 mb-2">
            <span className={result.success ? "text-emerald-400" : "text-red-400"}>
              {result.success ? "✓ Éxito" : "✗ Error"}
            </span>
          </div>
          {result.output && (
            <pre className="text-gray-300 whitespace-pre-wrap">{result.output}</pre>
          )}
          {result.error && (
            <pre className="text-red-400 whitespace-pre-wrap">{result.error}</pre>
          )}
        </div>
      )}
    </div>
  );
}