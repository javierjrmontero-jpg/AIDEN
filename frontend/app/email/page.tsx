"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

interface EmailItem {
  id: string;
  subject: string;
  from: string;
  date: string;
  body: string;
  account?: string;
  account_id?: string;
  error?: boolean;
}

interface EmailAccount {
  id: string;
  provider: string;
  email_address: string;
  enabled: boolean;
}

export default function Email() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<EmailAccount[]>([]);
  const [emails, setEmails] = useState<EmailItem[]>([]);
  const [selected, setSelected] = useState<EmailItem | null>(null);
  const [tab, setTab] = useState<"inbox" | "compose" | "settings">("inbox");
  const [selectedAccount, setSelectedAccount] = useState<string>("all");
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
  const [fromAccount, setFromAccount] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("mate_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    loadAccounts(t);
  }, [router]);

  const loadAccounts = async (t: string) => {
    try {
      const res = await fetch("/api/v1/email/config", {
        headers: { "Authorization": `Bearer ${t}` }
      });
      const data = await res.json();
      setAccounts(data);
      if (data.length > 0) {
        loadInbox(t);
        setFromAccount(data[0].id);
      }
    } catch (e) { console.error(e); }
  };

  const loadInbox = async (t: string, accountId?: string) => {
    setLoadingEmails(true);
    try {
      const url = accountId && accountId !== "all"
        ? `/api/v1/email/inbox?limit=20&account_id=${accountId}`
        : "/api/v1/email/inbox?limit=20";
      const res = await fetch(url, { headers: { "Authorization": `Bearer ${t}` } });
      if (res.ok) setEmails(await res.json());
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
      setEmailAddress(""); setAppPassword("");
      setTimeout(() => setSaved(false), 2000);
      loadAccounts(token);
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const deleteAccount = async (id: string) => {
    if (!token) return;
    await fetch(`/api/v1/email/config/${id}`, {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${token}` }
    });
    loadAccounts(token);
  };

  const sendEmail = async () => {
    if (!token || !to || !subject || !body) return;
    setSending(true);
    try {
      await fetch("/api/v1/email/send", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ to, subject, body, account_id: fromAccount || null })
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
    setBody(`\n\n--- Mensaje original ---\nDe: ${email.from}\n\n${email.body}`);
    if (email.account_id) setFromAccount(email.account_id);
    setTab("compose");
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString("es-AR", {
        day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"
      });
    } catch { return dateStr; }
  };

  const providerIcon: Record<string, string> = {
    gmail: "🔴", outlook: "🔵", yahoo: "🟣"
  };

  const providerGuide: Record<string, string> = {
    gmail: "Necesitás una App Password de Google → myaccount.google.com/apppasswords",
    outlook: "Usá tu contraseña de Outlook o App Password → account.microsoft.com/security",
    yahoo: "Necesitás una App Password de Yahoo → login.yahoo.com/account/security",
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
          <span className="text-xs text-gray-600 ml-auto">by JJRM</span>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          {(["inbox", "compose", "settings"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === t ? "bg-emerald-600 text-white" : "bg-gray-800 text-gray-400 hover:text-gray-200"
              }`}>
              {t === "inbox" ? "📥 Bandeja" : t === "compose" ? "✏️ Redactar" : "⚙️ Cuentas"}
            </button>
          ))}
          {tab === "inbox" && accounts.length > 0 && (
            <button onClick={() => token && loadInbox(token, selectedAccount)}
              className="ml-auto px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs text-gray-400 transition-colors">
              ↻ Actualizar
            </button>
          )}
        </div>

        {/* Bandeja */}
        {tab === "inbox" && (
          accounts.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-500 text-sm mb-3">No hay cuentas configuradas</p>
              <button onClick={() => setTab("settings")}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm transition-colors">
                Agregar cuenta
              </button>
            </div>
          ) : (
            <div>
              {/* Filtro por cuenta */}
              {accounts.length > 1 && (
                <div className="flex gap-2 mb-4">
                  <button onClick={() => { setSelectedAccount("all"); token && loadInbox(token); }}
                    className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                      selectedAccount === "all" ? "bg-emerald-600 text-white" : "bg-gray-800 text-gray-400"
                    }`}>
                    Todas las cuentas
                  </button>
                  {accounts.map(a => (
                    <button key={a.id}
                      onClick={() => { setSelectedAccount(a.id); token && loadInbox(token, a.id); }}
                      className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                        selectedAccount === a.id ? "bg-emerald-600 text-white" : "bg-gray-800 text-gray-400"
                      }`}>
                      {providerIcon[a.provider]} {a.email_address.split("@")[0]}
                    </button>
                  ))}
                </div>
              )}

              <div className="grid grid-cols-3 gap-4">
                {/* Lista */}
                <div className="col-span-1 space-y-1 max-h-[600px] overflow-y-auto">
                  {loadingEmails ? (
                    <p className="text-xs text-gray-600 text-center py-8">Cargando...</p>
                  ) : emails.length === 0 ? (
                    <p className="text-xs text-gray-600 text-center py-8">Bandeja vacía</p>
                  ) : (
                    emails.map((email) => (
                      <div key={`${email.account_id}-${email.id}`} onClick={() => setSelected(email)}
                        className={`px-3 py-3 rounded-xl cursor-pointer transition-colors border ${
                          selected?.id === email.id && selected?.account_id === email.account_id
                            ? "bg-gray-700 border-emerald-700"
                            : "bg-gray-900 border-gray-800 hover:border-gray-700"
                        } ${email.error ? "opacity-50" : ""}`}>
                        {accounts.length > 1 && (
                          <p className="text-xs text-gray-600 mb-0.5">
                            {providerIcon[accounts.find(a => a.id === email.account_id)?.provider || ""] || "📧"} {email.account?.split("@")[0]}
                          </p>
                        )}
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
                        {selected.account && (
                          <p className="text-xs text-gray-600">Para: {selected.account}</p>
                        )}
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
            </div>
          )
        )}

        {/* Redactar */}
        {tab === "compose" && (
          accounts.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-500 text-sm mb-3">Configurá una cuenta primero</p>
              <button onClick={() => setTab("settings")}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm transition-colors">
                Agregar cuenta
              </button>
            </div>
          ) : (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
              <h3 className="text-sm font-semibold mb-4">Nuevo mensaje</h3>
              <div className="space-y-3">
                {accounts.length > 1 && (
                  <div>
                    <label className="text-xs text-gray-400 mb-1 block">Enviar desde</label>
                    <select value={fromAccount} onChange={(e) => setFromAccount(e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 transition-colors text-gray-100">
                      {accounts.map(a => (
                        <option key={a.id} value={a.id}>
                          {providerIcon[a.provider]} {a.email_address}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
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

        {/* Cuentas */}
        {tab === "settings" && (
          <div className="space-y-4">
            {/* Cuentas existentes */}
            {accounts.length > 0 && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-800">
                  <h3 className="text-sm font-semibold">Cuentas configuradas</h3>
                </div>
                <div className="divide-y divide-gray-800">
                  {accounts.map(a => (
                    <div key={a.id} className="flex items-center gap-3 px-4 py-3">
                      <span className="text-lg">{providerIcon[a.provider] || "📧"}</span>
                      <div className="flex-1">
                        <p className="text-sm text-gray-200">{a.email_address}</p>
                        <p className="text-xs text-gray-500 capitalize">{a.provider}</p>
                      </div>
                      <button onClick={() => deleteAccount(a.id)}
                        className="p-1 rounded hover:bg-red-900 text-gray-600 hover:text-red-400 transition-colors">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="3 6 5 6 21 6"/>
                          <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                          <path d="M10 11v6M14 11v6"/>
                          <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Agregar nueva cuenta */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
              <h3 className="text-sm font-semibold mb-1">Agregar cuenta</h3>
              <p className="text-xs text-gray-500 mb-4">Podés agregar múltiples cuentas de diferentes proveedores</p>
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-gray-400 mb-1 block">Proveedor</label>
                  <select value={provider} onChange={(e) => setProvider(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 transition-colors text-gray-100">
                    <option value="gmail">🔴 Gmail</option>
                    <option value="outlook">🔵 Outlook / Hotmail</option>
                    <option value="yahoo">🟣 Yahoo Mail</option>
                  </select>
                </div>
                <div className="bg-blue-900/20 border border-blue-800 rounded-lg p-3">
                  <p className="text-xs text-blue-300">{providerGuide[provider]}</p>
                </div>
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
                  ) : saved ? "✓ Cuenta agregada" : "Agregar cuenta"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}