"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { CSSProperties } from "react";
import { useRouter } from "next/navigation";

const API_URL = "";

const SEG = 28;
const VU = 32;

interface Vitals {
  cpu: number;
  cpu_cores: number;
  memory: number;
  memory_used_gb: number;
  memory_total_gb: number;
  disk: number;
  disk_free_gb: number;
  temperature: number | null;
  uptime_seconds: number;
  processes: number;
  net_rx_mbps: number;
  net_tx_mbps: number;
}

interface Vault {
  documents: number;
  chunks: number;
  memories: number;
  processing: { filename: string; size_bytes: number; started_at: string } | null;
}

interface CalEvent {
  id?: string;
  title?: string;
  summary?: string;
  start?: string;
  account?: string;
  error?: boolean;
}

interface Task {
  id: string;
  title: string;
  due_date?: string | null;
  completed: boolean;
}

interface Conv {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

type LogKind = "ok" | "warn" | "err" | "net" | "vlt";

interface LogLine {
  id: number;
  time: string;
  kind: LogKind;
  text: string;
}

const KIND_LABEL: Record<LogKind, string> = {
  ok: "NÚCLEO",
  warn: "AVISO",
  err: "FALLO",
  net: "RED",
  vlt: "BÓVEDA",
};

const KIND_COLOR: Record<LogKind, string> = {
  ok: "#58C08E",
  warn: "#E8A33D",
  err: "#E5544B",
  net: "#3FBFB0",
  vlt: "#8B9FD1",
};

const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

const pad = (n: number) => String(n).padStart(2, "0");

function relTime(then: Date, now: Date): string {
  const s = Math.max(0, Math.floor((now.getTime() - then.getTime()) / 1000));
  if (s < 60) return "hace instantes";
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h`;
  return `hace ${Math.floor(s / 86400)} d`;
}

export default function Hud() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);

  const [vitals, setVitals] = useState<Vitals | null>(null);
  const [vault, setVault] = useState<Vault | null>(null);
  const [events, setEvents] = useState<CalEvent[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [convs, setConvs] = useState<Conv[]>([]);
  const [log, setLog] = useState<LogLine[]>([]);
  const [now, setNow] = useState(new Date());
  const [online, setOnline] = useState(true);
  const [micOn, setMicOn] = useState(false);
  const [micError, setMicError] = useState("");

  const netHist = useRef<number[]>(new Array(90).fill(0));
  const netCanvas = useRef<HTMLCanvasElement>(null);
  const waveCanvas = useRef<HTMLCanvasElement>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const logId = useRef(0);
  const analyser = useRef<AnalyserNode | null>(null);
  const audioCtx = useRef<AudioContext | null>(null);
  const [inLevel, setInLevel] = useState(0);

  const push = useCallback((kind: LogKind, text: string) => {
    const d = new Date();
    setLog((prev) => {
      const next = [
        ...prev,
        { id: logId.current++, time: `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`, kind, text },
      ];
      return next.length > 60 ? next.slice(-60) : next;
    });
  }, []);

  /* ── Sesión ─────────────────────────────────────────────────────── */
  useEffect(() => {
    const t = localStorage.getItem("mate_token");
    if (!t) { router.replace("/login"); return; }
    setToken(t);
    push("ok", "Consola montada — sesión verificada");
  }, [router, push]);

  const authFetch = useCallback(
    async (path: string) => {
      const res = await fetch(`${API_URL}${path}`, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    [token]
  );

  /* ── Reloj ──────────────────────────────────────────────────────── */
  useEffect(() => {
    const i = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(i);
  }, []);

  /* ── Vitales cada 2 s ───────────────────────────────────────────── */
  useEffect(() => {
    if (!token) return;
    let alive = true;
    const tick = async () => {
      try {
        const v: Vitals = await authFetch("/api/v1/system/vitals");
        if (!alive) return;
        setVitals(v);
        setOnline(true);
        const h = netHist.current;
        h.push(Math.min(1, (v.net_rx_mbps + v.net_tx_mbps) / 12));
        h.shift();
      } catch {
        if (alive) setOnline(false);
      }
    };
    tick();
    const i = setInterval(tick, 2000);
    return () => { alive = false; clearInterval(i); };
  }, [token, authFetch]);

  /* ── Bóveda cada 5 s ────────────────────────────────────────────── */
  useEffect(() => {
    if (!token) return;
    let alive = true;
    let prevChunks = -1;
    const tick = async () => {
      try {
        const v: Vault = await authFetch("/api/v1/stats/vault");
        if (!alive) return;
        setVault(v);
        if (prevChunks >= 0 && v.chunks > prevChunks) {
          push("vlt", `${v.chunks - prevChunks} fragmento(s) indexado(s) — total ${v.chunks}`);
        }
        prevChunks = v.chunks;
      } catch { /* el estado de conexión ya lo marca vitales */ }
    };
    tick();
    const i = setInterval(tick, 5000);
    return () => { alive = false; clearInterval(i); };
  }, [token, authFetch, push]);

  /* ── Conversaciones cada 20 s ───────────────────────────────────── */
  useEffect(() => {
    if (!token) return;
    let alive = true;
    let prevTop = "";
    const tick = async () => {
      try {
        const c: Conv[] = await authFetch("/api/v1/conversations");
        if (!alive) return;
        const ordered = [...c].sort(
          (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        );
        setConvs(ordered);
        const top = ordered[0];
        if (prevTop && top && top.updated_at !== prevTop) {
          push("net", `Actividad en «${top.title || "sin título"}»`);
        }
        prevTop = top?.updated_at ?? "";
      } catch { /* el estado de conexión ya lo marca vitales */ }
    };
    tick();
    const i = setInterval(tick, 20000);
    return () => { alive = false; clearInterval(i); };
  }, [token, authFetch, push]);

  /* ── Agenda cada 60 s ───────────────────────────────────────────── */
  useEffect(() => {
    if (!token) return;
    let alive = true;
    const tick = async () => {
      try {
        const [ev, tk] = await Promise.all([
          authFetch("/api/v1/calendar/events").catch(() => ({ events: [] })),
          authFetch("/api/v1/tasks?completed=false").catch(() => []),
        ]);
        if (!alive) return;
        setEvents(Array.isArray(ev) ? ev : ev.events || []);
        setTasks(Array.isArray(tk) ? tk : []);
      } catch { /* ignorado */ }
    };
    tick();
    const i = setInterval(tick, 60000);
    return () => { alive = false; clearInterval(i); };
  }, [token, authFetch]);

  /* ── Traza de red ───────────────────────────────────────────────── */
  useEffect(() => {
    const cv = netCanvas.current;
    if (!cv) return;
    const cx = cv.getContext("2d");
    if (!cx) return;
    const r = window.devicePixelRatio || 1;
    const w = cv.clientWidth, h = cv.clientHeight;
    if (!w || !h) return;
    cv.width = w * r; cv.height = h * r;
    cx.setTransform(r, 0, 0, r, 0, 0);
    cx.clearRect(0, 0, w, h);

    cx.strokeStyle = "#1D2833";
    cx.lineWidth = 1;
    for (let i = 1; i < 4; i++) {
      const y = Math.round((h / 4) * i) + 0.5;
      cx.beginPath(); cx.moveTo(0, y); cx.lineTo(w, y); cx.stroke();
    }

    const hist = netHist.current;
    const pt = (i: number): [number, number] => [
      (i / (hist.length - 1)) * w,
      h - hist[i] * (h - 4) - 2,
    ];

    cx.beginPath();
    cx.moveTo(0, h);
    hist.forEach((_, i) => cx.lineTo(...pt(i)));
    cx.lineTo(w, h);
    cx.closePath();
    const g = cx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, "rgba(63,191,176,.22)");
    g.addColorStop(1, "rgba(63,191,176,0)");
    cx.fillStyle = g;
    cx.fill();

    cx.beginPath();
    hist.forEach((_, i) => {
      const [x, y] = pt(i);
      if (i) cx.lineTo(x, y); else cx.moveTo(x, y);
    });
    cx.strokeStyle = "#3FBFB0";
    cx.lineWidth = 1.5;
    cx.stroke();
  }, [vitals]);

  /* ── Audio real por micrófono ───────────────────────────────────── */
  const toggleMic = async () => {
    if (micOn) {
      audioCtx.current?.close();
      audioCtx.current = null;
      analyser.current = null;
      setMicOn(false);
      setInLevel(0);
      push("ok", "Entrada de audio cerrada");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ctx = new AudioContext();
      const src = ctx.createMediaStreamSource(stream);
      const an = ctx.createAnalyser();
      an.fftSize = 512;
      src.connect(an);
      audioCtx.current = ctx;
      analyser.current = an;
      setMicOn(true);
      setMicError("");
      push("ok", `Entrada de audio abierta — ${ctx.sampleRate / 1000} kHz`);
    } catch {
      setMicError("Sin permiso de micrófono");
      push("err", "El navegador denegó el acceso al micrófono");
    }
  };

  useEffect(() => {
    if (!micOn) return;
    let raf = 0;
    const buf = new Uint8Array(256);
    const draw = () => {
      const an = analyser.current;
      const cv = waveCanvas.current;
      if (an && cv) {
        an.getByteTimeDomainData(buf);
        let peak = 0;
        for (let i = 0; i < buf.length; i++) peak = Math.max(peak, Math.abs(buf[i] - 128) / 128);
        setInLevel(peak);

        const cx = cv.getContext("2d");
        if (cx) {
          const r = window.devicePixelRatio || 1;
          const w = cv.clientWidth, h = cv.clientHeight;
          cv.width = w * r; cv.height = h * r;
          cx.setTransform(r, 0, 0, r, 0, 0);
          cx.clearRect(0, 0, w, h);
          const mid = h / 2;
          cx.strokeStyle = "#1D2833";
          cx.lineWidth = 1;
          cx.beginPath(); cx.moveTo(0, mid + 0.5); cx.lineTo(w, mid + 0.5); cx.stroke();
          cx.strokeStyle = "#3FBFB0";
          cx.beginPath();
          for (let i = 0; i < buf.length; i++) {
            const x = (i / buf.length) * w;
            const y = mid + ((buf[i] - 128) / 128) * (mid - 3);
            if (i) cx.lineTo(x, y); else cx.moveTo(x, y);
          }
          cx.stroke();
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [micOn]);

  /* ── Auto-scroll del registro ───────────────────────────────────── */
  useEffect(() => {
    const el = feedRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [log]);

  /* ── Mandos ─────────────────────────────────────────────────────── */
  // El briefing no tiene pantalla propia: se ejecuta acá y reporta en el registro.
  const runBriefing = async () => {
    push("net", "Componiendo briefing del día…");
    try {
      const b = await authFetch("/api/v1/briefing");
      const texto = typeof b === "string" ? b : b.briefing || b.summary || "";
      push("ok", texto ? `Briefing listo — ${texto.slice(0, 90)}…` : "Briefing listo, sin contenido");
    } catch {
      push("err", "No se pudo componer el briefing");
    }
  };

  const commands = [
    { id: "chat", name: "Nueva conversación", key: "CTRL + K", run: () => router.push("/") },
    { id: "ingest", name: "Ingerir documento", key: "CTRL + I", run: () => router.push("/documents") },
    { id: "agent", name: "Agente autónomo", key: "CTRL + A", run: () => router.push("/agent") },
    { id: "brief", name: "Briefing del día", key: "CTRL + B", run: runBriefing },
    { id: "sync", name: "Agenda", key: "CTRL + S", run: () => router.push("/calendar") },
    { id: "tasks", name: "Tareas", key: "CTRL + T", run: () => router.push("/tasks") },
  ];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.ctrlKey || e.metaKey || e.altKey) return;
      const map: Record<string, string> = { k: "chat", i: "ingest", a: "agent", b: "brief", s: "sync", t: "tasks" };
      const id = map[e.key.toLowerCase()];
      if (!id) return;
      e.preventDefault();
      commands.find((c) => c.id === id)?.run();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  /* ── Derivados ──────────────────────────────────────────────────── */
  const uptime = vitals
    ? `${Math.floor(vitals.uptime_seconds / 3600)}h ${pad(Math.floor((vitals.uptime_seconds % 3600) / 60))}m`
    : "—";

  const agenda = [
    ...events.filter((e) => !e.error).map((e) => ({
      time: e.start ? new Date(e.start) : null,
      title: e.title || e.summary || "Evento",
      meta: e.account || "Calendario",
    })),
    ...tasks.map((t) => ({
      time: t.due_date ? new Date(t.due_date) : null,
      title: t.title,
      meta: "Tarea",
    })),
  ].sort((a, b) => (a.time?.getTime() ?? Infinity) - (b.time?.getTime() ?? Infinity));

  const nextIdx = agenda.findIndex((a) => a.time && a.time > now);

  return (
    <div style={S.page}>
      {/* React hoista este link al <head>; si Google Fonts no carga, caen las pilas de reserva */}
      <link
        rel="stylesheet"
        href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap"
      />
      <div style={S.scan} />

      <div style={S.hud}>
        {/* RIEL */}
        <header style={S.rail}>
          <div style={S.mark}>
            <b style={S.markB}>MATE</b>
            <span style={S.markS}>Consola de mando</span>
          </div>
          <div style={{ flex: 1 }} />
          <button onClick={() => router.push("/")} style={S.back}>← Volver</button>
          <div style={S.clockWrap}>
            <div style={S.clock}>{pad(now.getHours())}:{pad(now.getMinutes())}:{pad(now.getSeconds())}</div>
            <div style={S.clockSub}>{DIAS[now.getDay()]} {now.getDate()} {MESES[now.getMonth()]}</div>
          </div>
        </header>

        {/* REJILLA */}
        <div style={S.grid}>
          {/* IZQUIERDA */}
          <div style={{ ...S.col, gridTemplateRows: "auto 1fr" }}>
            <section style={S.panel}>
              <h2 style={S.h2}>Vitales del sistema<span style={S.tag}>{vitals ? `${vitals.cpu_cores} núcleos` : "—"}</span></h2>
              <div style={S.body}>
                <div style={{ display: "grid", gap: 13 }}>
                  <Meter label="Procesador" value={vitals?.cpu ?? 0} />
                  <Meter label="Memoria" value={vitals?.memory ?? 0}
                    note={vitals ? `${vitals.memory_used_gb} / ${vitals.memory_total_gb} GB` : ""} />
                  <Meter label="Almacenamiento" value={vitals?.disk ?? 0}
                    note={vitals ? `${vitals.disk_free_gb} GB libres` : ""} />
                </div>
                <div style={S.readouts}>
                  <Readout k="Temperatura" v={vitals?.temperature != null ? `${vitals.temperature} °C` : "n/d"} />
                  <Readout k="En servicio" v={uptime} />
                  <Readout k="Procesos" v={vitals ? String(vitals.processes) : "—"} />
                  <Readout k="Conexión" v={online ? "activa" : "caída"} />
                </div>
              </div>
            </section>

            <section style={S.panel}>
              <h2 style={S.h2}>Carga de red<span style={S.tag}>180 s</span></h2>
              <div style={{ ...S.body, display: "grid", alignContent: "start", gap: 10 }}>
                <canvas ref={netCanvas} style={{ display: "block", width: "100%", height: 74 }} />
                <div style={S.db}>
                  <span>↓ {vitals?.net_rx_mbps.toFixed(2) ?? "—"} MB/s</span>
                  <span>↑ {vitals?.net_tx_mbps.toFixed(2) ?? "—"} MB/s</span>
                </div>
              </div>
            </section>
          </div>

          {/* CENTRO */}
          <div style={{ ...S.col, gridTemplateRows: "auto 1fr" }}>
            <section style={S.panel}>
              <h2 style={S.h2}>Panel de mandos</h2>
              <div style={S.body}>
                <div style={S.mandos}>
                  {commands.map((c) => (
                    <button key={c.id} onClick={c.run} style={S.cmd}>
                      <span style={S.cmdN}>{c.name}</span>
                      <span style={S.cmdK}>{c.key}</span>
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <div style={S.midSplit}>
              <section style={S.panel}>
                <h2 style={S.h2}>
                  Conversaciones
                  <span style={S.tag}>{convs.length} en la bóveda</span>
                </h2>
                <div style={S.body}>
                  {convs.length === 0 ? (
                    <p style={S.empty}>Sin conversaciones todavía</p>
                  ) : (
                    convs.slice(0, 12).map((c, i) => (
                      <button
                        key={c.id}
                        onClick={() => router.push(`/?c=${c.id}`)}
                        style={{
                          ...S.conv,
                          borderLeftColor: i === 0 ? "#3FBFB0" : "#2A3946",
                          background: i === 0 ? "#141C25" : "transparent",
                        }}
                      >
                        <span style={{ ...S.convT, color: i === 0 ? "#3FBFB0" : "#C6D3DE" }}>
                          {c.title || "Sin título"}
                        </span>
                        <span style={S.convM}>
                          {i === 0 ? "en curso · " : ""}{relTime(new Date(c.updated_at), now)}
                        </span>
                      </button>
                    ))
                  )}
                </div>
              </section>

              <section style={S.panel}>
                <h2 style={S.h2}>Registro<span style={S.tag}>{log.length} entradas</span></h2>
                <div ref={feedRef} style={{ ...S.body, fontFamily: MONO, fontSize: 12, lineHeight: 1.65 }}>
                  {log.map((l) => (
                    <p key={l.id} style={{ margin: 0, display: "flex", gap: 9 }}>
                      <span style={{ color: "#45545F", flex: "none" }}>{l.time}</span>
                      <span style={{ color: KIND_COLOR[l.kind], flex: "none", width: 58, letterSpacing: ".06em" }}>
                        {KIND_LABEL[l.kind]}
                      </span>
                      <span style={{ color: "#6E8090" }}>{l.text}</span>
                    </p>
                  ))}
                </div>
              </section>
            </div>
          </div>

          {/* DERECHA */}
          <div style={{ ...S.col, gridTemplateRows: "1fr 1fr" }}>
            <section style={S.panel}>
              <h2 style={S.h2}>Agenda<span style={S.tag}>{now.getDate()} {MESES[now.getMonth()]}</span></h2>
              <div style={S.body}>
                {agenda.length === 0 ? (
                  <p style={S.empty}>Sin eventos ni tareas pendientes</p>
                ) : (
                  agenda.map((a, i) => {
                    const isNext = i === nextIdx;
                    const past = a.time ? a.time < now : false;
                    return (
                      <div key={i} style={{
                        ...S.ev,
                        borderLeftColor: isNext ? "#3FBFB0" : "#2A3946",
                        background: isNext ? "#141C25" : "transparent",
                        opacity: past && !isNext ? 0.42 : 1,
                      }}>
                        <div style={{ ...S.evH, color: isNext ? "#3FBFB0" : "#6E8090" }}>
                          {a.time ? `${pad(a.time.getHours())}:${pad(a.time.getMinutes())}` : "—:—"}
                        </div>
                        <div>
                          <div style={{ fontSize: 14, color: isNext ? "#3FBFB0" : "#C6D3DE" }}>{a.title}</div>
                          <div style={S.evM}>{a.meta}</div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </section>

            <section style={S.panel}>
              <h2 style={S.h2}>Bóveda<span style={S.tag}>en vivo</span></h2>
              <div style={S.body}>
                <div style={S.vaultNums}>
                  <VNum k="Documentos" v={vault?.documents ?? 0} d="en la bóveda" />
                  <VNum k="Fragmentos" v={vault?.chunks ?? 0} d="indexados" />
                  <VNum k="Memorias" v={vault?.memories ?? 0} d="extraídas" />
                  <VNum k="Estado" v={vault?.processing ? 1 : 0} d={vault?.processing ? "en proceso" : "en reposo"} />
                </div>

                {vault?.processing && (
                  <div style={S.ingest}>
                    <div style={S.ingestSt}>Ingiriendo</div>
                    <div style={S.ingestFn}>{vault.processing.filename}</div>
                    <div style={{ ...S.db, marginTop: 7 }}>
                      <span>{(vault.processing.size_bytes / 1024 ** 2).toFixed(1)} MB</span>
                      <span>
                        desde {new Date(vault.processing.started_at).toLocaleTimeString("es-AR", {
                          hour: "2-digit", minute: "2-digit",
                        })}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </section>
          </div>
        </div>

        {/* AUDIO */}
        <section style={S.panel}>
          <h2 style={S.h2}>
            Entrada / salida de audio
            <span style={S.tag}>{micError || (micOn ? "captando" : "en reposo")}</span>
          </h2>
          <div style={S.body}>
            <div style={S.audioGrid}>
              <div style={{ display: "grid", gap: 7 }}>
                <div style={S.chanHd}>
                  Entrada
                  <button onClick={toggleMic} style={S.micBtn}>
                    {micOn ? "Cerrar micrófono" : "Abrir micrófono"}
                  </button>
                </div>
                <Vu level={inLevel} />
                <div style={S.db}><span>-60</span><span>-24</span><span>-12</span><span>-6</span><span>0 dB</span></div>
              </div>

              <canvas ref={waveCanvas} style={{ display: "block", width: "100%", height: 56 }} />

              <div style={{ display: "grid", gap: 7 }}>
                <div style={S.chanHd}>
                  Salida
                  <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 11, color: "#45545F" }}>
                    Síntesis de voz — MATE
                  </span>
                </div>
                <Vu level={0} />
                <div style={S.db}><span>-60</span><span>-24</span><span>-12</span><span>-6</span><span>0 dB</span></div>
              </div>
            </div>
          </div>
        </section>

        {/* ESTADO */}
        <footer style={S.status}>
          <span><Dot color={online ? "#58C08E" : "#E5544B"} /><b style={S.statusB}>Núcleo</b> {online ? "operativo" : "sin respuesta"}</span>
          <span><b style={S.statusB}>Modelo</b> claude-sonnet-4-5</span>
          <span><b style={S.statusB}>Bóveda</b> Chroma + Neo4j</span>
          {vault?.processing && (
            <span><Dot color="#E8A33D" /><b style={S.statusB}>OCR</b> 1 en curso</span>
          )}
          <span style={{ marginLeft: "auto" }}>vitales cada 2 s · bóveda cada 5 s</span>
        </footer>
      </div>
    </div>
  );
}

/* ── Subcomponentes ───────────────────────────────────────────────── */

function segColor(pct: number) {
  return pct > 88 ? "#E5544B" : pct > 70 ? "#E8A33D" : "#3FBFB0";
}

function Meter({ label, value, note }: { label: string; value: number; note?: string }) {
  const on = Math.round((value / 100) * SEG);
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 5 }}>
        <span style={{ fontSize: 12, letterSpacing: ".12em", textTransform: "uppercase", color: "#6E8090" }}>{label}</span>
        {note && <span style={{ fontFamily: MONO, fontSize: 11, color: "#45545F" }}>{note}</span>}
        <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 14, fontVariantNumeric: "tabular-nums", color: "#C6D3DE" }}>
          {Math.round(value)}<span style={{ color: "#45545F", fontSize: 11 }}>%</span>
        </span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${SEG}, 1fr)`, gap: 2, height: 12 }}>
        {Array.from({ length: SEG }, (_, i) => (
          <span key={i} style={{
            background: i < on ? segColor(((i + 1) / SEG) * 100) : "#1D2833",
            transition: "background .18s linear",
          }} />
        ))}
      </div>
    </div>
  );
}

function Vu({ level }: { level: number }) {
  const on = Math.round(level * VU);
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${VU}, 1fr)`, gap: 2, height: 16 }}>
      {Array.from({ length: VU }, (_, i) => {
        const p = (i + 1) / VU;
        return (
          <span key={i} style={{
            background: i < on ? (p > 0.92 ? "#E5544B" : p > 0.78 ? "#E8A33D" : "#3FBFB0") : "#1D2833",
          }} />
        );
      })}
    </div>
  );
}

function Readout({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <div style={{ fontSize: 11, letterSpacing: ".13em", textTransform: "uppercase", color: "#45545F" }}>{k}</div>
      <div style={{ fontFamily: MONO, fontSize: 15, fontVariantNumeric: "tabular-nums", color: "#C6D3DE" }}>{v}</div>
    </div>
  );
}

function VNum({ k, v, d }: { k: string; v: number; d: string }) {
  return (
    <div>
      <div style={{ fontSize: 11, letterSpacing: ".13em", textTransform: "uppercase", color: "#45545F" }}>{k}</div>
      <div style={{ fontFamily: MONO, fontSize: 24, fontVariantNumeric: "tabular-nums", color: "#8B9FD1", lineHeight: 1.15 }}>
        {v.toLocaleString("es-AR")}
      </div>
      <div style={{ fontSize: 12, color: "#45545F", fontFamily: MONO }}>{d}</div>
    </div>
  );
}

function Dot({ color }: { color: string }) {
  return <span style={{ display: "inline-block", width: 6, height: 6, background: color, marginRight: 6, verticalAlign: 1 }} />;
}

/* ── Estilos ──────────────────────────────────────────────────────── */

const MONO = '"JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace';
const UI = '"Barlow Semi Condensed", "Barlow", ui-sans-serif, system-ui, sans-serif';

const S: Record<string, CSSProperties> = {
  page: { background: "#080B0F", color: "#C6D3DE", fontFamily: UI, fontSize: 14, minHeight: "100vh" },
  scan: {
    position: "fixed", inset: 0, pointerEvents: "none", zIndex: 50,
    background:
      "repeating-linear-gradient(to bottom, rgba(255,255,255,.014) 0 1px, transparent 1px 3px)," +
      "radial-gradient(ellipse at 50% 40%, transparent 55%, rgba(0,0,0,.45) 100%)",
  },
  hud: { height: "100vh", display: "grid", gridTemplateRows: "auto 1fr auto auto", gap: 10, padding: 10 },
  rail: { display: "flex", alignItems: "center", gap: 20, padding: "10px 14px", background: "#0F151C", border: "1px solid #1D2833" },
  mark: { display: "flex", alignItems: "baseline", gap: 9 },
  markB: { fontFamily: MONO, fontWeight: 700, fontSize: 17, letterSpacing: ".12em", color: "#3FBFB0" },
  markS: { fontSize: 12, letterSpacing: ".16em", textTransform: "uppercase", color: "#45545F" },
  back: { background: "transparent", border: "1px solid #2A3946", color: "#6E8090", font: "inherit", padding: "5px 11px", cursor: "pointer" },
  clockWrap: { textAlign: "right" },
  clock: { fontFamily: MONO, fontSize: 22, fontWeight: 500, fontVariantNumeric: "tabular-nums", letterSpacing: ".04em" },
  clockSub: { fontSize: 11, letterSpacing: ".14em", textTransform: "uppercase", color: "#45545F" },
  grid: { display: "grid", gridTemplateColumns: "300px minmax(0, 1fr) 330px", gap: 10, minHeight: 0 },
  col: { display: "grid", gap: 10, minHeight: 0 },
  panel: { background: "#0F151C", border: "1px solid #1D2833", display: "flex", flexDirection: "column", minHeight: 0 },
  h2: {
    margin: 0, padding: "8px 12px 7px", fontSize: 11, fontWeight: 600, letterSpacing: ".2em",
    textTransform: "uppercase", color: "#6E8090", borderBottom: "1px solid #1D2833",
    display: "flex", alignItems: "center", gap: 8, flex: "none",
  },
  tag: { marginLeft: "auto", fontFamily: MONO, fontSize: 10, letterSpacing: ".08em", color: "#45545F", textTransform: "none" },
  body: { padding: 12, minHeight: 0, overflow: "auto" },
  readouts: {
    marginTop: 14, paddingTop: 12, borderTop: "1px solid #1D2833",
    display: "grid", gridTemplateColumns: "1fr 1fr", gap: "11px 8px",
  },
  db: { fontFamily: MONO, fontSize: 11, fontVariantNumeric: "tabular-nums", color: "#45545F", display: "flex", justifyContent: "space-between" },
  mandos: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 },
  cmd: {
    textAlign: "left", font: "inherit", color: "#C6D3DE", background: "#141C25",
    border: "1px solid #2A3946", padding: "10px 11px 9px", cursor: "pointer", display: "grid", gap: 3,
  },
  cmdN: { fontSize: 14, fontWeight: 500 },
  cmdK: { fontFamily: MONO, fontSize: 10, letterSpacing: ".06em", color: "#45545F" },
  midSplit: { display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", gap: 10, minHeight: 0 },
  conv: {
    display: "grid", gap: 2, width: "100%", textAlign: "left", font: "inherit",
    background: "transparent", border: "none", borderLeft: "2px solid #2A3946",
    padding: "8px 10px", cursor: "pointer",
  },
  convT: { fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  convM: { fontFamily: MONO, fontSize: 11, color: "#45545F" },
  ev: { display: "grid", gridTemplateColumns: "52px 1fr", gap: 11, padding: "9px 10px", borderLeft: "2px solid #2A3946" },
  evH: { fontFamily: MONO, fontSize: 13, fontVariantNumeric: "tabular-nums" },
  evM: { fontSize: 12, letterSpacing: ".06em", textTransform: "uppercase", color: "#45545F", marginTop: 1 },
  empty: { fontSize: 13, color: "#45545F", textAlign: "center", padding: "18px 0" },
  vaultNums: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px 8px", marginBottom: 14 },
  ingest: { paddingTop: 12, borderTop: "1px solid #1D2833" },
  ingestSt: { fontSize: 12, letterSpacing: ".1em", textTransform: "uppercase", color: "#E8A33D", marginBottom: 6 },
  ingestFn: { fontFamily: MONO, fontSize: 12, color: "#C6D3DE", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  audioGrid: { display: "grid", gridTemplateColumns: "1fr 210px 1fr", gap: 18, alignItems: "center" },
  chanHd: { display: "flex", alignItems: "baseline", gap: 9, fontSize: 11, letterSpacing: ".18em", textTransform: "uppercase", color: "#6E8090" },
  micBtn: {
    marginLeft: "auto", background: "transparent", border: "1px solid #2A3946", color: "#6E8090",
    font: "inherit", fontSize: 11, letterSpacing: ".06em", textTransform: "none", padding: "3px 9px", cursor: "pointer",
  },
  status: {
    display: "flex", alignItems: "center", gap: 22, padding: "7px 14px", background: "#0F151C",
    border: "1px solid #1D2833", fontFamily: MONO, fontSize: 11, letterSpacing: ".04em", color: "#45545F", flexWrap: "wrap",
  },
  statusB: { color: "#6E8090", fontWeight: 400 },
};
