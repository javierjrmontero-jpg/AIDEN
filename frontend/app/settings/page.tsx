"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SettingsPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [assistantName, setAssistantName] = useState("MATE");
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("mate_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    fetch("/api/v1/settings", { headers: { Authorization: `Bearer ${t}` } })
      .then(r => r.json())
      .then(d => { if (d.assistant_name) setAssistantName(d.assistant_name); })
      .catch(() => {});
  }, [router]);

  const save = async () => {
    if (!token) return;
    setLoading(true);
    try {
      await fetch("/api/v1/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ assistant_name: assistantName.trim() || "MATE" }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-md bg-gray-900 border border-gray-800 rounded-2xl p-8 space-y-6">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push("/")}
            className="text-gray-500 hover:text-gray-300 transition-colors text-sm">
            ← Volver
          </button>
          <h1 className="text-lg font-semibold text-blue-400">Configuración</h1>
        </div>

        <div className="space-y-2">
          <label className="text-xs text-gray-400">Nombre del asistente</label>
          <input
            type="text"
            value={assistantName}
            onChange={e => setAssistantName(e.target.value)}
            maxLength={30}
            placeholder="MATE"
            className="w-full bg-gray-800 border border-gray-700 focus:border-blue-400 rounded-xl px-4 py-3 text-sm outline-none transition-colors text-gray-100 placeholder-gray-600"
          />
          <p className="text-xs text-gray-600">
            Este nombre aparece en la UI, en el sistema y en la voz.
          </p>
        </div>

        <button onClick={save} disabled={loading}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-xl text-sm font-medium transition-colors">
          {loading ? "Guardando..." : saved ? "✓ Guardado" : "Guardar"}
        </button>
      </div>
    </div>
  );
}
