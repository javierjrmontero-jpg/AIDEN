"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useGoBack } from "@/components/useGoBack";

interface CalEvent {
  id: string;
  summary: string;
  description?: string;
  location?: string;
  start: string;
  end: string;
  all_day?: boolean;
  html_link?: string;
  account?: string;
  error?: boolean;
}

interface CalAccount {
  id: string;
  provider: string;
  google_email: string;
  calendar_id: string;
  enabled: boolean;
}

function fmt(iso: string, allDay?: boolean) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (allDay) return d.toLocaleDateString("es-AR", { weekday: "short", day: "numeric", month: "short" });
    return d.toLocaleString("es-AR", {
      weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function Calendar() {
  const router = useRouter();
  const goBack = useGoBack();
  const [token, setToken] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<CalAccount[]>([]);
  const [events, setEvents] = useState<CalEvent[]>([]);
  const [tab, setTab] = useState<"agenda" | "create" | "connect">("agenda");
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(7);

  // Conexión
  const [refreshToken, setRefreshToken] = useState("");
  const [savingConn, setSavingConn] = useState(false);
  const [connMsg, setConnMsg] = useState("");

  // Crear evento
  const [summary, setSummary] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [createMsg, setCreateMsg] = useState("");

  const loadEvents = useCallback(async (t: string, d: number) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/calendar/events?days=${d}&limit=20`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (res.ok) setEvents(await res.json());
      else setEvents([]);
    } catch {
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAccounts = useCallback(async (t: string) => {
    try {
      const res = await fetch("/api/v1/calendar/config", {
        headers: { Authorization: `Bearer ${t}` },
      });
      const data = await res.json();
      setAccounts(data);
      if (data.length > 0) loadEvents(t, days);
    } catch (e) {
      console.error(e);
    }
  }, [days, loadEvents]);

  useEffect(() => {
    const t = localStorage.getItem("mate_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    loadAccounts(t);
  }, [router, loadAccounts]);

  const saveConnection = async () => {
    if (!token || !refreshToken.trim()) return;
    setSavingConn(true);
    setConnMsg("");
    try {
      const res = await fetch("/api/v1/calendar/config", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ refresh_token: refreshToken.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setConnMsg(`Conectado: ${data.google_email}`);
        setRefreshToken("");
        loadAccounts(token);
      } else {
        setConnMsg(data.detail || "Error al conectar");
      }
    } catch {
      setConnMsg("Error de red");
    } finally {
      setSavingConn(false);
    }
  };

  const deleteAccount = async (id: string) => {
    if (!token) return;
    await fetch(`/api/v1/calendar/config/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    loadAccounts(token);
  };

  const createEvent = async () => {
    if (!token || !summary.trim() || !start) return;
    setCreating(true);
    setCreateMsg("");
    try {
      const res = await fetch("/api/v1/calendar/events", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          summary, start, end: end || "", location, description,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setCreateMsg("Evento creado");
        setSummary(""); setStart(""); setEnd(""); setLocation(""); setDescription("");
        loadEvents(token, days);
      } else {
        setCreateMsg(data.detail || "Error al crear");
      }
    } catch {
      setCreateMsg("Error de red");
    } finally {
      setCreating(false);
    }
  };

  const tabBtn = (id: typeof tab, label: string) => (
    <button
      onClick={() => setTab(id)}
      className={`px-4 py-2 rounded-lg text-sm transition-colors ${
        tab === id ? "bg-emerald-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
      }`}
    >
      {label}
    </button>
  );

  const input = "w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 focus:outline-none focus:border-emerald-500";

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <button
            onClick={() => goBack()}
            className="p-2 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors"
          >
            ←
          </button>
          <h1 className="font-semibold text-lg">Calendario</h1>
          {accounts.length > 0 && (
            <span className="text-xs text-gray-600 ml-auto">{accounts[0].google_email}</span>
          )}
        </div>

        <div className="flex gap-2 mb-6">
          {tabBtn("agenda", "Agenda")}
          {tabBtn("create", "Nuevo evento")}
          {tabBtn("connect", "Conexión")}
        </div>

        {/* AGENDA */}
        {tab === "agenda" && (
          <div>
            {accounts.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-500 text-sm mb-3">No hay calendarios conectados.</p>
                <button
                  onClick={() => setTab("connect")}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm transition-colors"
                >
                  Conectar Google Calendar
                </button>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-xs text-gray-500">Próximos</span>
                  {[7, 14, 30].map((d) => (
                    <button
                      key={d}
                      onClick={() => { setDays(d); if (token) loadEvents(token, d); }}
                      className={`px-2.5 py-1 rounded-md text-xs transition-colors ${
                        days === d ? "bg-gray-700 text-gray-100" : "bg-gray-800 text-gray-500 hover:bg-gray-700"
                      }`}
                    >
                      {d} días
                    </button>
                  ))}
                  <button
                    onClick={() => token && loadEvents(token, days)}
                    className="ml-auto px-3 py-1 bg-gray-800 hover:bg-gray-700 rounded-md text-xs text-gray-400 transition-colors"
                  >
                    Actualizar
                  </button>
                </div>

                {loading ? (
                  <p className="text-xs text-gray-600 text-center py-8">Cargando agenda…</p>
                ) : events.length === 0 ? (
                  <p className="text-xs text-gray-600 text-center py-8">Sin eventos en el rango.</p>
                ) : (
                  <div className="space-y-2">
                    {events.map((e, i) => (
                      <div
                        key={e.id + i}
                        className={`bg-gray-900 rounded-xl border p-4 ${
                          e.error ? "border-red-900" : "border-gray-800"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-sm font-medium text-gray-100">{e.summary}</span>
                          <span className="text-xs text-gray-500 whitespace-nowrap">
                            {e.error ? "" : fmt(e.start, e.all_day)}
                          </span>
                        </div>
                        {e.location && <p className="text-xs text-gray-500 mt-1">📍 {e.location}</p>}
                        {e.description && (
                          <p className="text-xs text-gray-600 mt-1 line-clamp-2">{e.description}</p>
                        )}
                        {e.html_link && (
                          <a
                            href={e.html_link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-emerald-500 hover:text-emerald-400 mt-2 inline-block"
                          >
                            Abrir en Google →
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* CREAR */}
        {tab === "create" && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 space-y-3 max-w-xl">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Título *</label>
              <input className={input} value={summary} onChange={(e) => setSummary(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Inicio *</label>
                <input type="datetime-local" className={input} value={start} onChange={(e) => setStart(e.target.value)} />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Fin (opcional, +1h)</label>
                <input type="datetime-local" className={input} value={end} onChange={(e) => setEnd(e.target.value)} />
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Ubicación</label>
              <input className={input} value={location} onChange={(e) => setLocation(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Descripción</label>
              <textarea className={input} rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
            <button
              onClick={createEvent}
              disabled={creating || !summary.trim() || !start}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 rounded-lg text-sm transition-colors"
            >
              {creating ? "Creando…" : "Crear evento"}
            </button>
            {createMsg && <p className="text-xs text-gray-400">{createMsg}</p>}
          </div>
        )}

        {/* CONEXIÓN */}
        {tab === "connect" && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 space-y-4 max-w-xl">
            <div>
              <h2 className="text-sm font-semibold text-gray-100 mb-2">Cuentas conectadas</h2>
              {accounts.length === 0 ? (
                <p className="text-xs text-gray-600">Ninguna.</p>
              ) : (
                <div className="space-y-2">
                  {accounts.map((a) => (
                    <div key={a.id} className="flex items-center justify-between bg-gray-800 rounded-lg px-3 py-2">
                      <span className="text-xs text-gray-200">{a.google_email}</span>
                      <button
                        onClick={() => deleteAccount(a.id)}
                        className="text-xs text-red-400 hover:text-red-300"
                      >
                        Desconectar
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-gray-800">
              <h2 className="text-sm font-semibold text-gray-100 mb-2">Conectar nueva cuenta</h2>
              <p className="text-xs text-gray-500 mb-3 leading-relaxed">
                Generá el <code className="text-emerald-500">refresh_token</code> ejecutando{" "}
                <code className="text-gray-300">scripts/google_calendar_auth.py</code> en tu PC y pegalo acá.
              </p>
              <textarea
                className={input}
                rows={3}
                placeholder="1//0g... (refresh token)"
                value={refreshToken}
                onChange={(e) => setRefreshToken(e.target.value)}
              />
              <button
                onClick={saveConnection}
                disabled={savingConn || !refreshToken.trim()}
                className="mt-3 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 rounded-lg text-sm transition-colors"
              >
                {savingConn ? "Validando…" : "Conectar"}
              </button>
              {connMsg && <p className="text-xs text-gray-400 mt-2">{connMsg}</p>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
