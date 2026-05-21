"use client";

import { useState } from "react";

interface Props {
  content: string;
  token: string;
}

export default function MessageActions({ content, token }: Props) {
  const [downloading, setDownloading] = useState(false);
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error("Error copiando:", e);
    }
  };

  const download = async (format: string) => {
    setDownloading(true);
    try {
      const res = await fetch(`/api/v1/generate/document`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          content,
          format,
          filename: "mate_respuesta"
        })
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `mate_respuesta.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Error descargando:", e);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="flex items-center gap-1 mt-3 pt-2 border-t border-gray-700">
      <button
        onClick={copyToClipboard}
        className="flex items-center gap-1 px-2 py-1 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 hover:text-white text-xs transition-all"
      >
        {copied ? "✓ Copiado" : "📋 Copiar"}
      </button>

      <div className="flex items-center gap-1 ml-2">
        <span className="text-xs text-gray-600">Descargar:</span>
        {["md", "txt", "html"].map((fmt) => (
          <button
            key={fmt}
            onClick={() => download(fmt)}
            disabled={downloading}
            className="px-2 py-1 rounded-lg bg-gray-700 hover:bg-emerald-700 text-gray-300 hover:text-white text-xs font-mono transition-all disabled:opacity-50"
          >
            .{fmt}
          </button>
        ))}
      </div>
    </div>
  );
}
