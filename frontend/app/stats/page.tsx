"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useGoBack } from "@/components/useGoBack";

export default function Stats() {
  const router = useRouter();
  const goBack = useGoBack();
  const [token, setToken] = useState<string | null>(null);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem("mate_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    loadStats(t);
  }, [router]);

  const loadStats = async (t: string) => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/stats/personal", {
        headers: { "Authorization": `Bearer ${t}` }
      });
      setData(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const maxActivity = data
    ? Math.max(...data.daily_activity.map((d: any) => d.conversations), 1)
    : 1;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 px-4 py-8">
      <div className="max-w-3xl mx-auto">

        <div className="flex items-center gap-3 mb-8">
          <button onClick={() => goBack()}
            className="p-2 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </button>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="font-semibold">MATE</span>
          </div>
          <span className="text-sm text-gray-500 ml-1">Estadísticas</span>
          <button onClick={() => token && loadStats(token)}
            className="ml-auto px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs text-gray-400 transition-colors">
            ↻ Actualizar
          </button>
        </div>

        {loading ? (
          <p className="text-center text-gray-600 py-12">Cargando...</p>
        ) : data && (
          <div className="space-y-4">

            {/* Resumen */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: "Conversaciones", value: data.conversations.total, icon: "💬", sub: `${data.conversations.this_week} esta semana` },
                { label: "Mensajes", value: data.messages.total, icon: "✉️", sub: `${data.messages.by_user} tuyos` },
                { label: "Tareas", value: data.tasks.total, icon: "✅", sub: `${data.tasks.completion_rate}% completadas` },
                { label: "Documentos", value: data.documents, icon: "📄", sub: `${data.memories} memorias` },
              ].map((item) => (
                <div key={item.label} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
                  <div className="text-2xl mb-1">{item.icon}</div>
                  <div className="text-2xl font-bold text-emerald-400">{item.value}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{item.label}</div>
                  <div className="text-xs text-gray-600 mt-0.5">{item.sub}</div>
                </div>
              ))}
            </div>

            {/* Actividad últimos 7 días */}
            <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
              <h3 className="text-sm font-semibold mb-4">Actividad — últimos 7 días</h3>
              <div className="flex items-end gap-2 h-32">
                {data.daily_activity.map((day: any, i: number) => (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1">
                    <span className="text-xs text-gray-600">{day.conversations || ""}</span>
                    <div className="w-full rounded-t-lg transition-all"
                      style={{
                        height: `${Math.max((day.conversations / maxActivity) * 96, day.conversations > 0 ? 8 : 2)}px`,
                        backgroundColor: day.conversations > 0 ? "#059669" : "#1f2937"
                      }}
                    />
                    <span className="text-xs text-gray-500">{day.day}</span>
                    <span className="text-xs text-gray-700">{day.date}</span>
                  </div>
                ))}
              </div>
              {data.most_active_day && data.most_active_day.conversations > 0 && (
                <p className="text-xs text-gray-500 mt-3">
                  Día más activo: <span className="text-emerald-400">{data.most_active_day.day} {data.most_active_day.date}</span> con {data.most_active_day.conversations} conversaciones
                </p>
              )}
            </div>

            {/* Tareas */}
            <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
              <h3 className="text-sm font-semibold mb-4">Progreso de tareas</h3>
              <div className="flex items-center gap-4 mb-3">
                <div className="flex-1 bg-gray-700 rounded-full h-3">
                  <div className="bg-emerald-500 h-3 rounded-full transition-all"
                    style={{ width: `${data.tasks.completion_rate}%` }} />
                </div>
                <span className="text-sm font-bold text-emerald-400">{data.tasks.completion_rate}%</span>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <p className="text-lg font-bold text-gray-200">{data.tasks.total}</p>
                  <p className="text-xs text-gray-500">Total</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-emerald-400">{data.tasks.completed}</p>
                  <p className="text-xs text-gray-500">Completadas</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-yellow-400">{data.tasks.pending}</p>
                  <p className="text-xs text-gray-500">Pendientes</p>
                </div>
              </div>
            </div>

            {/* Mensajes */}
            <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
              <h3 className="text-sm font-semibold mb-4">Distribución de mensajes</h3>
              <div className="flex gap-4">
                <div className="flex-1">
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>Tus mensajes</span>
                    <span>{data.messages.by_user}</span>
                  </div>
                  <div className="bg-gray-700 rounded-full h-2">
                    <div className="bg-blue-500 h-2 rounded-full"
                      style={{ width: `${data.messages.total > 0 ? (data.messages.by_user / data.messages.total * 100) : 0}%` }} />
                  </div>
                </div>
                <div className="flex-1">
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>Respuestas de MATE</span>
                    <span>{data.messages.by_mate}</span>
                  </div>
                  <div className="bg-gray-700 rounded-full h-2">
                    <div className="bg-emerald-500 h-2 rounded-full"
                      style={{ width: `${data.messages.total > 0 ? (data.messages.by_mate / data.messages.total * 100) : 0}%` }} />
                  </div>
                </div>
              </div>
            </div>

            {/* Miembro desde */}
            <p className="text-xs text-gray-600 text-center">
              Usando MATE desde {data.member_since}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}