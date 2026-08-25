"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useGoBack } from "@/components/useGoBack";

export default function Memories() {
  const router = useRouter();
  const goBack = useGoBack();
  const [token, setToken] = useState<string | null>(null);
  const [memories, setMemories] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem("mate_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    loadMemories(t);
  }, [router]);

  const loadMemories = async (t: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/memories`, {
        headers: { "Authorization": `Bearer ${t}` }
      });
      const data = await res.json();
      setMemories(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const deleteMemory = async (id: string) => {
    if (!token) return;
    await fetch(`/api/v1/memories/${id}`, {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${token}` }
    });
    loadMemories(token);
  };

  const categoryColor: Record<string, string> = {
    proyecto: "bg-blue-900 text-blue-300",
    tecnologia: "bg-purple-900 text-purple-300",
    preferencia: "bg-yellow-900 text-yellow-300",
    problema: "bg-red-900 text-red-300",
    personal: "bg-green-900 text-green-300",
    general: "bg-gray-700 text-gray-300",
  };

  const categoryIcon: Record<string, string> = {
    proyecto: "🗂",
    tecnologia: "⚙️",
    preferencia: "⭐",
    problema: "🔧",
    personal: "👤",
    general: "📌",
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 px-4 py-8">
      <div className="max-w-2xl mx-auto">

        <div className="flex items-center gap-3 mb-8">
          <button
            onClick={() => goBack()}
            className="text-gray-500 hover:text-gray-300 transition-colors"
          >
            ← Volver
          </button>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="font-semibold">MATE</span>
          </div>
          <span className="text-xs text-gray-600 ml-auto">by JJRM</span>
        </div>

        <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold">Memorias</h2>
            <span className="text-xs text-gray-500">{memories.length} guardadas</span>
          </div>
          <p className="text-xs text-gray-500 mb-6">
            Lo que MATE recuerda de tus conversaciones anteriores
          </p>

          {loading ? (
            <p className="text-xs text-gray-600 text-center py-8">Cargando...</p>
          ) : memories.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-600 text-sm">No hay memorias guardadas aún</p>
              <p className="text-gray-700 text-xs mt-2">
                MATE extrae memorias automáticamente al finalizar conversaciones
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {memories.map((mem) => (
                <div
                  key={mem.id}
                  className="flex items-start gap-3 bg-gray-800 rounded-xl px-4 py-3 group"
                >
                  <span className="text-lg mt-0.5">
                    {categoryIcon[mem.category] || "📌"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-200">{mem.content}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${categoryColor[mem.category] || categoryColor.general}`}>
                        {mem.category}
                      </span>
                      <span className="text-xs text-gray-600">
                        Importancia: {Math.round(mem.importance * 100)}%
                      </span>
                      <span className="text-xs text-gray-700">
                        {new Date(mem.created_at).toLocaleDateString("es-AR")}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => deleteMemory(mem.id)}
                    className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 transition-all text-xs mt-1"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <p className="text-xs text-gray-700 text-center mt-4">
          Las memorias se generan automáticamente y podés eliminar cualquiera
        </p>
      </div>
    </div>
  );
}
