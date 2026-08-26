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
  disk_scope?: string;
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

/* La maquetación vive acá y no en los objetos inline: las media queries no
   existen en `style`, y sin ellas la consola no se adapta a pantallas chicas. */
const HUD_CSS = `
.hud-root  { height:100vh; display:grid; grid-template-rows:auto 1fr auto auto; gap:10px; padding:10px; }
.hud-grid  { display:grid; grid-template-columns:300px minmax(0,1fr) 330px; gap:10px; min-height:0; }
.hud-col   { display:grid; gap:10px; min-height:0; }
.hud-col-l { grid-template-rows:auto 1fr; }
.hud-col-m { grid-template-rows:auto auto 1fr; }
.hud-col-r { grid-template-rows:1fr 1fr; }
.hud-mid   { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:10px; min-height:0; }
.hud-audio { display:grid; grid-template-columns:1fr 210px 1fr; gap:18px; align-items:center; }
.hud-mandos{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }

.hud-root button:focus-visible { outline:2px solid #3FBFB0; outline-offset:1px; }
.hud-rail button:hover { border-color:#2A3946; color:#C6D3DE; }
.hud-rail [data-tauri-drag-region] { cursor:default; }
.hud-root ::-webkit-scrollbar { width:8px; height:8px; }
.hud-root ::-webkit-scrollbar-thumb { background:#2A3946; }
.hud-root ::-webkit-scrollbar-track { background:transparent; }

@media (max-width:1180px) {
  .hud-root  { height:auto; }
  .hud-grid  { grid-template-columns:1fr; }
  .hud-col-l, .hud-col-m, .hud-col-r { grid-template-rows:auto; }
  .hud-mid   { grid-template-columns:1fr; }
  .hud-audio { grid-template-columns:1fr; gap:14px; }
  .hud-col > section, .hud-mid > section { min-height:240px; }
  .hud-body  { overflow:visible !important; }
}
@media (max-width:640px) {
  .hud-mandos { grid-template-columns:1fr 1fr; }
  .hud-rail   { flex-wrap:wrap; }
}
@media (prefers-reduced-motion: reduce) {
  .hud-root *, .hud-root *::before, .hud-root *::after {
    transition-duration:.001ms !important; animation-duration:.001ms !important;
  }
}
`;

/* ── Ventana nativa ─────────────────────────────────────────────────
   La app de escritorio corre sin marco, así que la consola tiene que
   aportar el arrastre y los controles. En el navegador no existe
   `__TAURI__` y todo esto simplemente no se muestra. */

interface TauriWin {
  minimize: () => Promise<void>;
  toggleMaximize: () => Promise<void>;
  close: () => Promise<void>;
}

function ventanaNativa(): TauriWin | null {
  if (typeof window === "undefined") return null;
  const t = (window as unknown as {
    __TAURI__?: { window?: { getCurrentWindow?: () => TauriWin } };
  }).__TAURI__;
  return t?.window?.getCurrentWindow?.() ?? null;
}

function ControlesVentana() {
  const [nativa, setNativa] = useState<TauriWin | null>(null);

  // Se resuelve tras montar: en SSR no hay window, y el global de Tauri
  // se inyecta antes del script de la página pero no durante el prerender.
  useEffect(() => setNativa(ventanaNativa()), []);
  if (!nativa) return null;

  const B = ({ onClick, label, d }: { onClick: () => void; label: string; d: string }) => (
    <button onClick={onClick} aria-label={label} title={label} style={S.winBtn}>
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
        <path d={d} stroke="currentColor" strokeWidth="1.2" fill="none" />
      </svg>
    </button>
  );

  return (
    <div style={{ display: "flex", gap: 2, marginLeft: 8 }}>
      <B onClick={() => nativa.minimize()} label="Minimizar" d="M1 5h8" />
      <B onClick={() => nativa.toggleMaximize()} label="Maximizar" d="M1.5 1.5h7v7h-7z" />
      <B onClick={() => nativa.close()} label="Cerrar" d="M1.5 1.5l7 7M8.5 1.5l-7 7" />
    </div>
  );
}

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
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const [transcribing, setTranscribing] = useState(false);

  // Detección de voz en el navegador: abre la captura al detectar habla y la
  // cierra tras el silencio, para no transcribir ambiente.
  const ultimoSonido = useRef(0);
  const inicioGrab = useRef(0);
  const inicioVoz = useRef(0);
  // El bucle de audio corre fuera de React: lee estos espejos, no el estado.
  const hablandoRef = useRef(false);
  const ocupadoRef = useRef(false);
  const [capturando, setCapturando] = useState(false);
  const [escuchaContinua, setEscuchaContinua] = useState(false);
  const [said, setSaid] = useState("");
  const [reply, setReply] = useState("");
  const [asking, setAsking] = useState(false);
  const hudConv = useRef<string | null>(null);
  // `iniciarCaptura` es estable, asi que su onstop captura el closure del
  // primer render, cuando todavia no habia token. Va por ref para que
  // siempre invoque la version actual.
  const procesarVozRef = useRef<(b: Blob) => Promise<void>>(async () => {});

  const UMBRAL_VOZ = 0.08;      // pico normalizado por encima del ruido de sala
  const ARRANQUE_MS = 160;      // voz sostenida antes de dar por iniciada la frase
  const SILENCIO_MS = 1500;     // silencio que da por terminada la frase
  const MAX_GRAB_MS = 20000;    // tope duro por si nunca detecta silencio
  const [inLevel, setInLevel] = useState(0);
  const [outLevel, setOutLevel] = useState(0);
  const [speaking, setSpeaking] = useState(false);
  const [voiceName, setVoiceName] = useState("");

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

  /* ── Escucha continua ───────────────────────────────────────────────
     El micrófono queda abierto midiendo nivel, pero NO graba mientras no
     detecte voz: recién ahí abre el grabador, y lo cierra tras el silencio.
     Así no se transcribe ambiente ni se manda audio de una sala vacía. */

  const soltarMic = useCallback(() => {
    try { recorder.current?.stop(); } catch { /* ya detenido */ }
    recorder.current = null;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    audioCtx.current?.close();
    audioCtx.current = null;
    analyser.current = null;
    setMicOn(false);
    setCapturando(false);
    setInLevel(0);
  }, []);

  const abrirMic = useCallback(async (): Promise<boolean> => {
    if (stream.current) return true;
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      const ctx = new AudioContext();
      const an = ctx.createAnalyser();
      an.fftSize = 512;
      ctx.createMediaStreamSource(s).connect(an);
      stream.current = s;
      audioCtx.current = ctx;
      analyser.current = an;
      setMicOn(true);
      setMicError("");
      return true;
    } catch {
      setMicError("Sin permiso de micrófono");
      push("err", "El navegador denegó el acceso al micrófono");
      return false;
    }
  }, [push]);

  // Arranca una captura. La cierra el detector de silencio del bucle de audio.
  const iniciarCaptura = useCallback(() => {
    const s = stream.current;
    if (!s || recorder.current) return;

    const chunks: Blob[] = [];
    const mr = new MediaRecorder(s);
    mr.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
    mr.onstop = async () => {
      recorder.current = null;
      setCapturando(false);
      await procesarVozRef.current(new Blob(chunks, { type: "audio/webm" }));
    };
    mr.start();
    recorder.current = mr;
    inicioGrab.current = Date.now();
    setCapturando(true);
    push("net", "Voz detectada — capturando");
  }, [push]);

  // El orbe: fuerza el corte si ya está capturando, si no alterna la escucha.
  const toggleMic = async () => {
    if (transcribing || asking) return;
    if (recorder.current?.state === "recording") { recorder.current.stop(); return; }
    if (micOn) {
      soltarMic();
      setEscuchaContinua(false);
      push("ok", "Escucha detenida");
      return;
    }
    if (await abrirMic()) {
      setEscuchaContinua(true);
      push("ok", "Escucha continua activa — hablá cuando quieras");
    }
  };

  /* ── De voz a acción ─────────────────────────────────────────────── */
  const procesarVoz = async (blob: Blob) => {
    // Un fragmento minúsculo no contiene voz utilizable y el contenedor webm
    // sin cabecera completa hace fallar el decodificador del backend.
    if (blob.size < 4000) {
      push("warn", `Fragmento demasiado corto (${blob.size} B) — descartado`);
      return;
    }

    setTranscribing(true);
    push("net", `Transcribiendo ${(blob.size / 1024).toFixed(0)} KB…`);
    try {
      const fd = new FormData();
      fd.append("file", blob, "audio.webm");
      fd.append("language", "es-AR");
      const res = await fetch(`${API_URL}/api/v1/transcribe`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (!res.ok) {
        const detalle = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status} ${detalle.slice(0, 200)}`);
      }
      const { text } = await res.json();
      const dicho = (text || "").trim();
      if (!dicho) { push("warn", "No se entendió nada"); return; }

      push("ok", `«${dicho}»`);

      const mando = reconocerMando(dicho);
      if (mando) {
        push("ok", `Ejecutando: ${mando.name}`);
        mando.run();
      } else {
        await preguntarAMate(dicho);
      }
    } catch (e) {
      push("err", `Transcripción fallida — ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setTranscribing(false);
    }
  };
  procesarVozRef.current = procesarVoz;

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

        // Detector: abre la captura con voz sostenida, la cierra con silencio.
        // Mientras MATE habla no se escucha, o se transcribiría a sí mismo.
        const ahora = Date.now();
        const hayVoz = peak > UMBRAL_VOZ;
        if (hayVoz) {
          ultimoSonido.current = ahora;
          if (!inicioVoz.current) inicioVoz.current = ahora;
        } else if (!recorder.current) {
          inicioVoz.current = 0;
        }

        const grabando = recorder.current?.state === "recording";
        if (!grabando) {
          const sostenida = inicioVoz.current && ahora - inicioVoz.current > ARRANQUE_MS;
          if (sostenida && !hablandoRef.current && !ocupadoRef.current) iniciarCaptura();
        } else {
          const callado = ahora - ultimoSonido.current > SILENCIO_MS;
          const pasado = ahora - inicioGrab.current > MAX_GRAB_MS;
          if (callado || pasado) {
            inicioVoz.current = 0;
            recorder.current?.stop();
          }
        }

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

  /* ── Consulta hablada: se resuelve acá, no en el chat ───────────────
     La consola mantiene su propia conversación, así hablar no te saca de
     la pantalla. La respuesta se lee en voz alta por el canal de salida. */
  const preguntarAMate = async (pregunta: string) => {
    setAsking(true);
    setSaid(pregunta);
    setReply("");
    push("net", "Consultando a MATE…");

    try {
      const res = await fetch(`${API_URL}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          messages: [{ role: "user", content: pregunta }],
          conversation_id: hudConv.current,
          voice: true,
        }),
      });
      if (!res.ok) throw new Error(String(res.status));

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let completo = "";

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lineas = buffer.split("\n");
        buffer = lineas.pop() || "";

        for (const linea of lineas) {
          if (!linea.startsWith("data: ")) continue;
          const bruto = linea.slice(6).trim();
          if (bruto === "[DONE]") continue;

          let texto: string;
          try { texto = JSON.parse(bruto); } catch { texto = bruto; }
          if (typeof texto !== "string") continue;

          // La consola reutiliza su propia conversación entre preguntas
          if (texto.startsWith("[CONV:")) { hudConv.current = texto.slice(6, -1); continue; }
          if (texto.startsWith("[STATUS:tool:")) {
            push("net", `Herramienta: ${texto.replace("[STATUS:tool:", "").replace("]", "").trim()}`);
            continue;
          }
          if (texto.startsWith("[STATUS:") || texto.startsWith("[CONFIRM_EMAIL:")) continue;

          completo += texto;
          setReply(completo);
        }
      }

      if (completo.trim()) {
        push("ok", "Respuesta recibida");
        hablar(completo);
      } else {
        push("warn", "MATE no devolvió texto");
      }
    } catch {
      push("err", "No se pudo consultar a MATE");
      setReply("No se pudo consultar a MATE.");
    } finally {
      setAsking(false);
    }
  };

  /* ── Voz de salida ──────────────────────────────────────────────────
     speechSynthesis no expone su audio a Web Audio, así que el medidor
     refleja actividad: cada palabra pronunciada lo hace latir. */
  const hablar = (texto: string) => {
    if (!window.speechSynthesis) { push("warn", "Este navegador no tiene síntesis de voz"); return; }

    const limpio = texto
      .replace(/```[\s\S]*?```/g, " (bloque de código) ")
      .replace(/[*_#`>]/g, "")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/\s+/g, " ")
      .trim();
    if (!limpio) return;

    const u = new SpeechSynthesisUtterance(limpio);
    u.lang = "es-AR";
    const voz = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith("es"));
    if (voz) { u.voice = voz; setVoiceName(voz.name); }

    u.onstart = () => setSpeaking(true);
    u.onboundary = () => {
      setOutLevel(0.35 + Math.random() * 0.5);
      setTimeout(() => setOutLevel((l) => l * 0.4), 120);
    };
    u.onend = () => { setSpeaking(false); setOutLevel(0); };
    u.onerror = () => { setSpeaking(false); setOutLevel(0); push("err", "Falló la síntesis de voz"); };

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  };

  /* ── Prueba de salida ───────────────────────────────────────────────
     speechSynthesis no expone su audio a Web Audio, así que no hay
     amplitud real que medir. El medidor refleja actividad: cada palabra
     pronunciada dispara un evento `boundary` que lo hace latir. */
  const testOutput = () => {
    push("ok", "Probando canal de salida");
    hablar("Consola MATE. Canal de salida verificado. Todos los sistemas responden.");
  };

  // Espejos para el bucle de audio
  useEffect(() => { hablandoRef.current = speaking; }, [speaking]);
  useEffect(() => { ocupadoRef.current = transcribing || asking; }, [transcribing, asking]);

  /* Arranque: la consola escucha desde que abre, salvo que lo hayas
     apagado antes. El permiso ya concedido no se vuelve a pedir. */
  useEffect(() => {
    if (!token) return;
    if (localStorage.getItem("mate_escucha") === "off") {
      push("ok", "Escucha apagada — tocá el orbe para activarla");
      return;
    }
    abrirMic().then((ok) => {
      if (ok) {
        setEscuchaContinua(true);
        push("ok", "Escucha continua activa — hablá cuando quieras");
      }
    });
  }, [token, abrirMic, push]);

  // Recordar la preferencia entre sesiones
  useEffect(() => {
    if (!token) return;
    localStorage.setItem("mate_escucha", escuchaContinua ? "on" : "off");
  }, [escuchaContinua, token]);

  /* Al salir de la consola hay que soltar el micrófono, o el navegador
     sigue mostrando la pestaña como grabando. */
  useEffect(() => soltarMic, [soltarMic]);

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

  /* Palabras que disparan un mando de la consola. Todo lo demás va al chat,
     que es donde MATE razona: acá solo resolvemos lo que la consola hace. */
  const VOZ: Record<string, string[]> = {
    chat: ["nueva conversación", "nuevo chat", "conversación nueva"],
    ingest: ["documento", "documentos", "subir", "ingerir", "bóveda"],
    agent: ["agente", "autónomo"],
    brief: ["briefing", "resumen del día", "parte del día"],
    sync: ["agenda", "calendario"],
    tasks: ["tarea", "tareas", "pendientes"],
  };

  const reconocerMando = (dicho: string) => {
    const t = dicho.toLowerCase();
    // Solo tratamos como mando las frases cortas: "abrí tareas" sí,
    // "¿qué tareas tengo para el jueves?" es una pregunta para MATE.
    if (t.split(/\s+/).length > 5) return null;
    for (const [id, claves] of Object.entries(VOZ)) {
      if (claves.some((k) => t.includes(k))) return commands.find((c) => c.id === id) ?? null;
    }
    return null;
  };

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
  const orbState: OrbState =
    speaking ? "speaking"
    : asking || transcribing ? "thinking"
    : capturando ? "listening"
    : micOn ? "armed"
    : "idle";
  const orbLevel = speaking ? outLevel : micOn ? inLevel : 0;

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
      <style>{HUD_CSS}</style>
      <div style={S.scan} />

      <div className="hud-root">
        {/* RIEL */}
        <header className="hud-rail" data-tauri-drag-region style={S.rail}>
          <div style={S.mark}>
            <b style={S.markB}>MATE</b>
            <span style={S.markS}>Consola de mando</span>
          </div>
          <div style={{ flex: 1 }} />
          <button onClick={() => router.push("/")} style={S.back}>Ir al chat →</button>
          <div style={S.clockWrap}>
            <div style={S.clock}>{pad(now.getHours())}:{pad(now.getMinutes())}:{pad(now.getSeconds())}</div>
            <div style={S.clockSub}>{DIAS[now.getDay()]} {now.getDate()} {MESES[now.getMonth()]}</div>
          </div>
          <ControlesVentana />
        </header>

        {/* REJILLA */}
        <div className="hud-grid">
          {/* IZQUIERDA */}
          <div className="hud-col hud-col-l">
            <section style={S.panel}>
              <h2 style={S.h2}>Vitales del sistema<span style={S.tag}>{vitals ? `${vitals.cpu_cores} núcleos` : "—"}</span></h2>
              <div className="hud-body" style={S.body}>
                <div style={{ display: "grid", gap: 13 }}>
                  <Meter label="Procesador" value={vitals?.cpu ?? 0} />
                  <Meter label="Memoria" value={vitals?.memory ?? 0}
                    note={vitals ? `${vitals.memory_used_gb} / ${vitals.memory_total_gb} GB` : ""} />
                  <Meter label="Almacenamiento" value={vitals?.disk ?? 0}
                    note={vitals ? `${vitals.disk_free_gb} GB libres · ${vitals.disk_scope ?? "contenedor"}` : ""} />
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
              <div className="hud-body" style={{ ...S.body, display: "grid", alignContent: "start", gap: 10 }}>
                <canvas ref={netCanvas} style={{ display: "block", width: "100%", height: 74 }} />
                <div style={S.db}>
                  <span>↓ {vitals?.net_rx_mbps.toFixed(2) ?? "—"} MB/s</span>
                  <span>↑ {vitals?.net_tx_mbps.toFixed(2) ?? "—"} MB/s</span>
                </div>
              </div>
            </section>
          </div>

          {/* CENTRO */}
          <div className="hud-col hud-col-m">
            <section style={{ ...S.panel, alignItems: "center", padding: "14px 0 12px" }}>
              <button
                onClick={toggleMic}
                disabled={transcribing || asking}
                title={micOn ? "Cortar y enviar" : "Hablarle a MATE"}
                style={S.orbBtn}
              >
                <Orb state={orbState} level={orbLevel} />
              </button>
            </section>

            <section style={S.panel}>
              <h2 style={S.h2}>Panel de mandos</h2>
              <div className="hud-body" style={S.body}>
                <div className="hud-mandos">
                  {commands.map((c) => (
                    <button key={c.id} onClick={c.run} style={S.cmd}>
                      <span style={S.cmdN}>{c.name}</span>
                      <span style={S.cmdK}>{c.key}</span>
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <div className="hud-mid">
              <section style={S.panel}>
                <h2 style={S.h2}>
                  Conversaciones
                  <span style={S.tag}>{convs.length} en la bóveda</span>
                </h2>
                <div className="hud-body" style={S.body}>
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
                <div ref={feedRef} className="hud-body" style={{ ...S.body, fontFamily: MONO, fontSize: 12, lineHeight: 1.65 }}>
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
          <div className="hud-col hud-col-r">
            <section style={S.panel}>
              <h2 style={S.h2}>Agenda<span style={S.tag}>{now.getDate()} {MESES[now.getMonth()]}</span></h2>
              <div className="hud-body" style={S.body}>
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
              <div className="hud-body" style={S.body}>
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
            <span style={S.tag}>
              {micError
                || (transcribing ? "transcribiendo"
                  : capturando ? "capturando"
                  : micOn ? "escucha continua"
                  : "apagado")}
            </span>
          </h2>
          <div className="hud-body" style={S.body}>
            <div className="hud-audio">
              <div style={{ display: "grid", gap: 7 }}>
                <div style={S.chanHd}>
                  Entrada
                  <button onClick={toggleMic} disabled={transcribing || asking} style={S.micBtn}>
                    {transcribing ? "Transcribiendo…"
                      : capturando ? "Cortar y enviar"
                      : micOn ? "Apagar escucha"
                      : "Activar escucha"}
                  </button>
                </div>
                <Vu level={inLevel} />
                <div style={S.db}>
                  <span>«tareas», «agenda», «documento» abren la pantalla</span>
                  <span>lo demás lo responde MATE</span>
                </div>
              </div>

              <canvas ref={waveCanvas} style={{ display: "block", width: "100%", height: 56 }} />

              <div style={{ display: "grid", gap: 7 }}>
                <div style={S.chanHd}>
                  Salida
                  <button onClick={testOutput} disabled={speaking} style={S.micBtn}>
                    {speaking ? "Hablando…" : "Probar salida"}
                  </button>
                </div>
                <Vu level={outLevel} />
                <div style={S.db}>
                  <span>Síntesis de voz — {voiceName || "voz del sistema"}</span>
                  <span>actividad</span>
                </div>
              </div>
            </div>

            {(said || reply || asking) && (
              <div style={S.exchange}>
                {said && (
                  <p style={S.said}>
                    <span style={S.who}>Vos</span>{said}
                  </p>
                )}
                <p style={S.reply}>
                  <span style={{ ...S.who, color: "#3FBFB0" }}>MATE</span>
                  {reply || (asking ? "pensando…" : "")}
                  {reply && !speaking && !asking && (
                    <button onClick={() => hablar(reply)} style={{ ...S.micBtn, marginLeft: 10 }}>
                      Repetir
                    </button>
                  )}
                </p>
              </div>
            )}
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

/* ── Orbe ───────────────────────────────────────────────────────────
   Un solo elemento que dice de un vistazo qué está haciendo la consola.
   No es decoración: el radio del núcleo sigue el nivel real de audio y
   cada estado tiene su propio comportamiento. */

type OrbState = "idle" | "armed" | "listening" | "thinking" | "speaking";

const ORB_LABEL: Record<OrbState, string> = {
  idle: "en espera",
  armed: "en escucha",
  listening: "escuchando",
  thinking: "procesando",
  speaking: "respondiendo",
};

function Orb({ state, level }: { state: OrbState; level: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const nivel = useRef(0);

  // El bucle se monta una sola vez: si dependiera de `level` se recrearia
  // en cada cuadro. Las props entran por refs, que siempre estan al dia.
  const estado = useRef(state);
  const objetivo = useRef(level);
  estado.current = state;
  objetivo.current = level;

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const cx = cv.getContext("2d");
    if (!cx) return;

    const quieto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let t = 0;

    const dibujar = () => {
      const r = window.devicePixelRatio || 1;
      const w = cv.clientWidth;
      const h = cv.clientHeight;
      if (!w || !h) { raf = requestAnimationFrame(dibujar); return; }
      cv.width = w * r;
      cv.height = h * r;
      cx.setTransform(r, 0, 0, r, 0, 0);
      cx.clearRect(0, 0, w, h);

      const cxp = w / 2;
      const cyp = h / 2;
      const base = Math.min(w, h) / 2 - 10;

      // El nivel persigue al valor real: evita saltos bruscos entre cuadros
      const state = estado.current;
      nivel.current += (objetivo.current - nivel.current) * 0.18;
      const n = nivel.current;

      const respira = quieto ? 0 : Math.sin(t * 0.03) * 0.5 + 0.5;
      const activo = state === "listening" || state === "speaking" || state === "thinking";

      // Halo
      const halo = cx.createRadialGradient(cxp, cyp, base * 0.1, cxp, cyp, base);
      const fuerza = 0.1 + (activo ? n * 0.45 : respira * 0.08);
      halo.addColorStop(0, `rgba(63,191,176,${0.26 + fuerza})`);
      halo.addColorStop(0.55, `rgba(63,191,176,${0.07 + fuerza * 0.3})`);
      halo.addColorStop(1, "rgba(63,191,176,0)");
      cx.fillStyle = halo;
      cx.beginPath();
      cx.arc(cxp, cyp, base, 0, Math.PI * 2);
      cx.fill();

      // Anillos que giran: al pensar aceleran y se abren
      const anillos = [
        { r: base * 0.86, vel: 0.006, arco: 1.5, ancho: 1 },
        { r: base * 0.72, vel: -0.011, arco: 0.9, ancho: 1.5 },
        { r: base * 0.58, vel: 0.017, arco: 2.3, ancho: 1 },
      ];
      const prisa = state === "thinking" ? 3.4 : 1;
      anillos.forEach((a, i) => {
        const giro = t * a.vel * prisa + i * 2.1;
        cx.beginPath();
        cx.arc(cxp, cyp, a.r, giro, giro + a.arco);
        cx.strokeStyle = `rgba(63,191,176,${state === "thinking" ? 0.75 : 0.4 + n * 0.4})`;
        cx.lineWidth = a.ancho;
        cx.stroke();
      });

      // Anillo de referencia, siempre presente
      cx.beginPath();
      cx.arc(cxp, cyp, base * 0.92, 0, Math.PI * 2);
      cx.strokeStyle = "rgba(63,191,176,.14)";
      cx.lineWidth = 1;
      cx.stroke();

      // Púas radiales: sólo cuando hay audio real que representar
      if (state === "listening" || state === "speaking") {
        const puas = 48;
        for (let i = 0; i < puas; i++) {
          const ang = (i / puas) * Math.PI * 2;
          const ruido = Math.abs(Math.sin(i * 12.9898 + t * 0.06));
          const largo = base * 0.1 + n * base * 0.3 * ruido;
          const r0 = base * 0.44;
          cx.beginPath();
          cx.moveTo(cxp + Math.cos(ang) * r0, cyp + Math.sin(ang) * r0);
          cx.lineTo(cxp + Math.cos(ang) * (r0 + largo), cyp + Math.sin(ang) * (r0 + largo));
          cx.strokeStyle =
            state === "speaking"
              ? `rgba(139,159,209,${0.35 + n * 0.5})`
              : `rgba(63,191,176,${0.35 + n * 0.5})`;
          cx.lineWidth = 1.5;
          cx.stroke();
        }
      }

      // Núcleo
      const rn = base * (0.26 + (activo ? n * 0.12 : respira * 0.03));
      const nucleo = cx.createRadialGradient(cxp, cyp, 0, cxp, cyp, rn);
      nucleo.addColorStop(0, "rgba(214,245,241,.95)");
      nucleo.addColorStop(0.45, `rgba(63,191,176,${0.8 + n * 0.2})`);
      nucleo.addColorStop(1, "rgba(31,107,100,0)");
      cx.fillStyle = nucleo;
      cx.beginPath();
      cx.arc(cxp, cyp, rn, 0, Math.PI * 2);
      cx.fill();

      t++;
      if (!quieto) raf = requestAnimationFrame(dibujar);
    };

    dibujar();
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div style={{ display: "grid", justifyItems: "center", gap: 6 }}>
      <canvas ref={ref} style={{ width: 190, height: 190, display: "block" }} />
      <span style={{
        fontFamily: MONO, fontSize: 10, letterSpacing: ".22em",
        textTransform: "uppercase", color: state === "idle" ? "#45545F" : "#3FBFB0",
      }}>
        {ORB_LABEL[state]}
      </span>
    </div>
  );
}

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
  rail: { display: "flex", alignItems: "center", gap: 20, padding: "10px 14px", background: "#0F151C", border: "1px solid #1D2833" },
  mark: { display: "flex", alignItems: "baseline", gap: 9 },
  markB: { fontFamily: MONO, fontWeight: 700, fontSize: 17, letterSpacing: ".12em", color: "#3FBFB0" },
  markS: { fontSize: 12, letterSpacing: ".16em", textTransform: "uppercase", color: "#45545F" },
  back: { background: "transparent", border: "1px solid #2A3946", color: "#6E8090", font: "inherit", padding: "5px 11px", cursor: "pointer" },
  clockWrap: { textAlign: "right" },
  clock: { fontFamily: MONO, fontSize: 22, fontWeight: 500, fontVariantNumeric: "tabular-nums", letterSpacing: ".04em" },
  clockSub: { fontSize: 11, letterSpacing: ".14em", textTransform: "uppercase", color: "#45545F" },
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
  cmd: {
    textAlign: "left", font: "inherit", color: "#C6D3DE", background: "#141C25",
    border: "1px solid #2A3946", padding: "10px 11px 9px", cursor: "pointer", display: "grid", gap: 3,
  },
  cmdN: { fontSize: 14, fontWeight: 500 },
  cmdK: { fontFamily: MONO, fontSize: 10, letterSpacing: ".06em", color: "#45545F" },
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
  chanHd: { display: "flex", alignItems: "baseline", gap: 9, fontSize: 11, letterSpacing: ".18em", textTransform: "uppercase", color: "#6E8090" },
  micBtn: {
    marginLeft: "auto", background: "transparent", border: "1px solid #2A3946", color: "#6E8090",
    font: "inherit", fontSize: 11, letterSpacing: ".06em", textTransform: "none", padding: "3px 9px", cursor: "pointer",
  },
  status: {
    display: "flex", alignItems: "center", gap: 22, padding: "7px 14px", background: "#0F151C",
    border: "1px solid #1D2833", fontFamily: MONO, fontSize: 11, letterSpacing: ".04em", color: "#45545F", flexWrap: "wrap",
  },
  exchange: {
    marginTop: 12, paddingTop: 12, borderTop: "1px solid #1D2833",
    display: "grid", gap: 6, maxHeight: 130, overflow: "auto",
  },
  who: {
    fontSize: 10, letterSpacing: ".16em", textTransform: "uppercase",
    color: "#45545F", marginRight: 10,
  },
  said: { margin: 0, fontSize: 13, color: "#6E8090" },
  reply: { margin: 0, fontSize: 14, color: "#C6D3DE", lineHeight: 1.5 },
  winBtn: {
    background: "transparent", border: "1px solid transparent", color: "#6E8090",
    width: 26, height: 22, display: "grid", placeItems: "center", cursor: "pointer", padding: 0,
  },
  orbBtn: {
    background: "transparent", border: "none", padding: 0,
    cursor: "pointer", display: "block", font: "inherit",
  },
  statusB: { color: "#6E8090", fontWeight: 400 },
};
