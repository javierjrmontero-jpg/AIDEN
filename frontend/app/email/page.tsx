"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

interface EmailItem {
  id: string;
  subject: string;
  from: string;
  date: string;
  body: string;
}

interface EmailConfig {
  configured: boolean;
  provider?: string;
  email_address?: string;
  enabled?: boolean;
}

export default function Email() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [config, setConfig] = useState<EmailConfig>({ configured: false });
  const [emails, setEmails] = useState<EmailItem[]>([]);
  const [selected, setSelected] = useState<EmailItem | null>(null);
  const [tab, setTab] = useState<"inbox" | "compose" | "settings">("inbox");
  const [loading, setLoading] = useState(false);
  const [loadingEmails, setLoadingEmails] = useState(false);

  // Config form
  const [provider, setProvider] = useState("gmail");
  const [emailAddress, setEmailAddress] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Compose form
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("mate_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    loadConfig(t);
  }, [router]);

  const loadConfig = async (t: string) => {
    try {
      const res = await fetch("/api/v1/email/config", {
        headers: { "Authorization": `Bearer ${t}` }
      });
      const data = await res.json();
      setConfig(data);
      if (data.configured) loadInbox(t);
    } catch (e) { console.error(e); }
  };

  const loadInbox = async (t: string) => {
    setLoadingEmails(true);
    try {
      const res = await fetch("/api/v1/email/inbox?limit=20", {
        headers: { "Authorization": `Bearer ${t}` }
      });
      setEmails(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoadingEmails(false); }
  };

  const saveConfig = async () => {
    if (!token || !emailAddress || !appPassword) return;
    setSaving(true);
    try {
      await fetch("/api/v1/email/config", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ provider, email_address: emailAddress, app_password: appPassword })
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      loadConfig(token);
      setTab("inbox");
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const sendEmail = async () => {
    if (!token || !to || !subject || !body) return;
    setSending(true);
    try {
      await fetch("/api/v1/email/send", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ to, subject, body })
      });
      setSent(true);
      setTo(""); setSubject(""); setBody("");
      setTimeout(() => setSent(false), 3000);
    } catch (e) { console.error(e); }
    finally { setSending(false); }
  };

  const replyWith = (email: EmailItem) => {
    setTo(email.from.match(/<(.+)>/)?.[1] || email.from);
    setSubject(`Re: ${email.subject}`);
    setBody(`\n\n--- Mensaje original ---\nDe: ${email.from}\nAsunto: ${email.subject}\n\n${email.body}`);
    setTab("compose");
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString("es-AR", {
        day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"
      });
    } catch { return dateStr; }
  };

  const providerGuide: Record<string, string> = {
    gmail: "Necesitás una App Password de Google. Generala en: myaccount.google.com/apppasswords",
    outlook: "Usá tu contraseña normal de Outlook. Si tenés 2FA, generá una App Password en account.microsoft.com/security",
    yahoo: "Necesitás una App Password de Yahoo. Generala en: login.yahoo.com/account/security",
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 px-4 py-8">
      <div className="max-w-4xl mx-auto">

        <div className="flex items-center gap-3 mb-8">
          <button onClick={() => router.push("/")}
            className="p-2 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </button>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="font-semibold">MATE</span>
          </div>
          <span className="text-sm text-gray-500 ml-1">Email</span>
          {config.configured && (
            <span className="text-xs text-gray-600">· {config.email_address}</span>
          )}
          <span className="text-xs text-gray-600 ml-auto">by JJRM</span>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          {(["inbox", "compose", "settings"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === t ? "bg-emerald-600 text-white" : "bg-gray-800 text-gray-400 hover:text-gray-200"
              }`}>
              {t === "inbox" ? "📥 Bandeja" : t === "compose" ? "✏️ Redactar" : "⚙️ Configurar"}
            </button>
          ))}
          {config.configured && tab === "inbox" && (
            <button onClick={() => token && loadInbox(token)}
              className="ml-auto px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs text-gray-400 transition-colors">
              ↻ Actualizar
            </button>
          )}
        </div>

        {/* Bandeja */}
        {tab === "inbox" && (
          !config.configured ? (
            <div className="text-center py-12">
              <p className="text-gray-500 text-sm mb-3">No hay email configurado</p>
              <button onClick={() => setTab("settings")}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm transition-colors">
                Configurar email
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-4">
              {/* Lista de emails */}
              <div className="col-span-1 space-y-1">
                {loadingEmails ? (
                  <p className="text-xs text-gray-600 text-center py-8">Cargando...</p>
                ) : emails.length === 0 ? (
                  <p className="text-xs text-gray-600 text-center py-8">Bandeja vacía</p>
                ) : (
                  emails.map((email) => (
                    <div key={email.id} onClick={() => setSelected(email)}
                      className={`px-3 py-3 rounded-xl cursor-pointer transition-colors border ${
                        selected?.id === email.id
                          ? "bg-gray-700 border-emerald-700"
                          : "bg-gray-900 border-gray-800 hover:border-gray-700"
                      }`}>
                      <p className="text-xs font-medium text-gray-200 truncate">
                        {email.from.split("<")[0].trim() || email.from}
                      </p>
                      <p className="text-xs text-gray-400 truncate mt-0.5">{email.subject}</p>
                      <p className="text-xs text-gray-600 mt-1">{formatDate(email.date)}</p>
                    </div>
                  ))
                )}
              </div>

              {/* Vista del email */}
              <div className="col-span-2">
                {selected ? (
                  <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
                    <div className="mb-4 pb-4 border-b border-gray-800">
                      <h3 className="text-sm font-semibold text-gray-100 mb-2">{selected.subject}</h3>
                      <p className="text-xs text-gray-500">De: {selected.from}</p>
                      <p className="text-xs text-gray-600">{formatDate(selected.date)}</p>
                    </div>
                    <pre className="text-xs text-gray-300 whitespace-pre-wrap font-sans leading-relaxed max-h-96 overflow-y-auto">
                      {selected.body}
                    </pre>
                    <div className="flex gap-2 mt-4 pt-4 border-t border-gray-800">
                      <button onClick={() => replyWith(selected)}
                        className="flex items-center gap-2 px-3 py-2 bg-emerald-700 hover:bg-emerald-600 rounded-lg text-xs transition-colors">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="9 17 4 12 9 7"/><path d="M20 18v-2a4 4 0 0 0-4-4H4"/>
                        </svg>
                        Responder
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-48 text-gray-600 text-sm">
                    Seleccioná un email para leerlo
                  </div>
                )}
              </div>
            </div>
          )
        )}

        {/* Redactar */}
        {tab === "compose" && (
          !config.configured ? (
            <div className="text-center py-12">
              <p className="text-gray-500 text-sm mb-3">Configurá tu email primero</p>
              <button onClick={() => setTab("settings")}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm transition-colors">
                Configurar email
              </button>
            </div>
          ) : (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
              <h3 className="text-sm font-semibold mb-4">Nuevo mensaje</h3>
              <div className="space-y-3">
                <input type="email" placeholder="Para *" value={to}
                  onChange={(e) => setTo(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-600 text-gray-100" />
                <input type="text" placeholder="Asunto *" value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-600 text-gray-100" />
                <textarea placeholder="Mensaje *" value={body}
                  onChange={(e) => setBody(e.target.value)} rows={10}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-600 resize-none text-gray-100" />
                <div className="flex items-center gap-3">
                  <button onClick={sendEmail} disabled={sending || !to || !subject || !body}
                    className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors">
                    {sending ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Enviando...
                      </>
                    ) : (
                      <>
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                        </svg>
                        Enviar
                      </>
                    )}
                  </button>
                  {sent && <span className="text-xs text-emerald-400">✓ Email enviado</span>}
                </div>
              </div>
            </div>
          )
        )}

        {/* Configuración */}
        {tab === "settings" && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
            <h3 className="text-sm font-semibold mb-1">Configuración de email</h3>
            <p className="text-xs text-gray-500 mb-5">
              Tus credenciales se guardan de forma segura y solo se usan para acceder a tu cuenta
            </p>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Proveedor</label>
                <select value={provider} onChange={(e) => setProvider(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 transition-colors text-gray-100">
                  <option value="gmail">Gmail</option>
                  <option value="outlook">Outlook / Hotmail</option>
                  <option value="yahoo">Yahoo Mail</option>
                </select>
              </div>

              {provider && (
                <div className="bg-blue-900/20 border border-blue-800 rounded-lg p-3">
                  <p className="text-xs text-blue-300">{providerGuide[provider]}</p>
                </div>
              )}

              <div>
                <label className="text-xs text-gray-400 mb-1 block">Dirección de email</label>
                <input type="email" placeholder="tu@gmail.com" value={emailAddress}
                  onChange={(e) => setEmailAddress(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-600 text-gray-100" />
              </div>

              <div>
                <label className="text-xs text-gray-400 mb-1 block">App Password</label>
                <input type="password" placeholder="xxxx xxxx xxxx xxxx" value={appPassword}
                  onChange={(e) => setAppPassword(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-600 text-gray-100" />
              </div>

              <button onClick={saveConfig} disabled={saving || !emailAddress || !appPassword}
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2">
                {saving ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Guardando...
                  </>
                ) : saved ? "✓ Guardado" : "Guardar configuración"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
