"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Admin() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [searchUsage, setSearchUsage] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [conversations, setConversations] = useState<any[]>([]);
  const [tab, setTab] = useState<"stats" | "users" | "conversations">("stats");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem("mate_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    loadData(t);
  }, [router]);

  const loadData = async (t: string) => {
    setLoading(true);
    try {
      const [s, u, c, su] = await Promise.all([
        fetch("/api/v1/admin/stats", { headers: { "Authorization": `Bearer ${t}` } }),
        fetch("/api/v1/admin/users", { headers: { "Authorization": `Bearer ${t}` } }),
        fetch("/api/v1/admin/conversations", { headers: { "Authorization": `Bearer ${t}` } }),
        fetch("/api/v1/admin/search-usage", { headers: { "Authorization": `Bearer ${t}` } })
      ]);
      setStats(await s.json());
      setUsers(await u.json());
      setConversations(await c.json());
      setSearchUsage(await su.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fmt = (iso: string) => new Date(iso).toLocaleDateString("es-AR", {
    day: "2-digit", month: "short", year: "numeric"
  });

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <button onClick={() => router.push("/")} className="text-gray-500 hover:text-gray-300">← Volver</button>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="font-semibold">MATE</span>
          </div>
          <span className="text-sm text-gray-500 ml-2">Panel de Administración</span>
          <span className="text-xs text-gray-600 ml-auto">by JJRM</span>
        </div>

        <div className="flex gap-2 mb-6">
          {(["stats", "users", "conversations"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === t ? "bg-emerald-600 text-white" : "bg-gray-800 text-gray-400 hover:text-gray-200"
              }`}>
              {t === "stats" ? "📊 Estadísticas" : t === "users" ? "👤 Usuarios" : "💬 Conversaciones"}
            </button>
          ))}
          <button onClick={() => token && loadData(token)}
            className="ml-auto px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs text-gray-400">
            ↻ Actualizar
          </button>
        </div>

        {loading ? <p className="text-center text-gray-600 py-12">Cargando...</p> : (
          <>
            {tab === "stats" && stats && (
              <div className="space-y-4">
                {/* Stats generales */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label: "Usuarios", value: stats.users, icon: "👤" },
                    { label: "Conversaciones", value: stats.conversations, icon: "💬" },
                    { label: "Esta semana", value: stats.conversations_this_week, icon: "📅" },
                    { label: "Mensajes", value: stats.messages, icon: "✉️" },
                    { label: "Documentos", value: stats.documents, icon: "📄" },
                    { label: "Memorias", value: stats.memories, icon: "🧠" },
                    { label: "DB", value: `${stats.db_size_mb} MB`, icon: "🗄️" },
                    { label: "VectorDB", value: `${stats.vectordb_size_mb} MB`, icon: "🔍" },
                  ].map((item) => (
                    <div key={item.label} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
                      <div className="text-2xl mb-1">{item.icon}</div>
                      <div className="text-2xl font-bold text-emerald-400">{item.value}</div>
                      <div className="text-xs text-gray-500 mt-1">{item.label}</div>
                    </div>
                  ))}
                </div>

                {/* Brave Search Usage */}
                {searchUsage && (
                  <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
                    <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                      🌐 Brave Search — Consumo
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                      {[
                        { label: "Total histórico", value: searchUsage.total_searches },
                        { label: "Esta semana", value: searchUsage.searches_this_week },
                        { label: "Este mes", value: searchUsage.searches_this_month },
                        { label: "Costo estimado mes", value: `USD ${searchUsage.cost_this_month_usd}` },
                      ].map((item) => (
                        <div key={item.label} className="text-center">
                          <div className="text-xl font-bold text-blue-400">{item.value}</div>
                          <div className="text-xs text-gray-500 mt-1">{item.label}</div>
                        </div>
                      ))}
                    </div>

                    {/* Barra de progreso del crédito gratuito */}
                    <div className="mt-2">
                      <div className="flex justify-between text-xs text-gray-500 mb-1">
                        <span>Crédito gratuito mensual (1000 requests)</span>
                        <span>{searchUsage.free_tier_remaining} restantes ({searchUsage.free_tier_percentage}%)</span>
                      </div>
                      <div className="w-full bg-gray-700 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all ${
                            searchUsage.free_tier_percentage > 50 ? "bg-emerald-500" :
                            searchUsage.free_tier_percentage > 20 ? "bg-yellow-500" : "bg-red-500"
                          }`}
                          style={{ width: `${searchUsage.free_tier_percentage}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-600 mt-1">
                        Costo total acumulado: USD {searchUsage.cost_total_usd}
                      </p>
                    </div>
                  </div>
                )}

                {/* Estado del sistema */}
                <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
                  <h3 className="text-sm font-semibold mb-3 text-gray-300">Estado del sistema</h3>
                  <div className="space-y-2">
                    {["Backend FastAPI", "Frontend Next.js", "Nginx HTTPS", "ChromaDB", "SQLite"].map((s) => (
                      <div key={s} className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                        <span className="text-xs text-gray-400">{s} — Online</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {tab === "users" && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-800">
                  <h3 className="text-sm font-semibold">{users.length} usuarios registrados</h3>
                </div>
                <div className="divide-y divide-gray-800">
                  {users.map((u) => (
                    <div key={u.id} className="flex items-center gap-4 px-4 py-3">
                      <div className="w-8 h-8 rounded-full bg-emerald-700 flex items-center justify-center text-sm font-bold">
                        {u.name[0].toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-200">{u.name}</p>
                        <p className="text-xs text-gray-500">{u.email}</p>
                        {u.role && <p className="text-xs text-gray-600">{u.role}</p>}
                      </div>
                      <div className="text-right">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          u.is_active ? "bg-emerald-900 text-emerald-400" : "bg-red-900 text-red-400"
                        }`}>
                          {u.is_active ? "Activo" : "Inactivo"}
                        </span>
                        <p className="text-xs text-gray-600 mt-1">{fmt(u.created_at)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === "conversations" && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-800">
                  <h3 className="text-sm font-semibold">Últimas {conversations.length} conversaciones</h3>
                </div>
                <div className="divide-y divide-gray-800">
                  {conversations.map((c) => (
                    <div key={c.id} className="flex items-center gap-4 px-4 py-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-gray-200 truncate">{c.title}</p>
                        <p className="text-xs text-gray-500">{c.user_name}</p>
                      </div>
                      <p className="text-xs text-gray-500">{fmt(c.updated_at)}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
