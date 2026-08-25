"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useGoBack } from "@/components/useGoBack";

export default function Profile() {
  const router = useRouter();
  const goBack = useGoBack();
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<{name: string; email: string} | null>(null);
  const [role, setRole] = useState("");
  const [context, setContext] = useState("");
  const [preferences, setPreferences] = useState("");
  const [language, setLanguage] = useState("es");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("mate_token");
    const u = localStorage.getItem("mate_user");
    if (!t || !u) { router.push("/login"); return; }
    setToken(t);
    setUser(JSON.parse(u));

    fetch(`/api/v1/auth/profile`, {
      headers: { "Authorization": `Bearer ${t}` }
    })
      .then(r => r.json())
      .then(data => {
        setRole(data.role || "");
        setContext(data.context || "");
        setPreferences(data.preferences || "");
        setLanguage(data.language || "es");
      });
  }, [router]);

  const save = async () => {
    if (!token) return;
    setSaving(true);
    await fetch(`/api/v1/auth/profile`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ role, context, preferences, language })
    });
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  if (!user) return null;

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-950 text-gray-100 px-4">
      <div className="w-full max-w-lg">

        <div className="flex items-center gap-3 mb-8">
          <button
            onClick={() => goBack()}
            className="p-2 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </button>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="font-semibold">MATE</span>
          </div>
          <span className="text-xs text-gray-600 ml-auto">by JJRM</span>
        </div>

        <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
          <h2 className="text-lg font-semibold mb-1">Tu perfil</h2>
          <p className="text-xs text-gray-500 mb-6">
            MATE usa esta información para personalizar sus respuestas
          </p>

          <div className="bg-gray-800 rounded-xl p-4 mb-6 flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-emerald-700 flex items-center justify-center text-lg font-bold flex-shrink-0">
              {user.name[0].toUpperCase()}
            </div>
            <div>
              <p className="text-sm font-medium">{user.name}</p>
              <p className="text-xs text-gray-500">{user.email}</p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Rol profesional</label>
              <input
                type="text"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="Ej: Arquitecto de software, Gerente de IT, DevOps Engineer..."
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-600 text-gray-100"
              />
            </div>

            <div>
              <label className="text-xs text-gray-400 mb-1 block">Contexto actual</label>
              <textarea
                value={context}
                onChange={(e) => setContext(e.target.value)}
                placeholder="Ej: Estoy construyendo un asistente virtual en RHEL 10 con FastAPI y Next.js..."
                rows={3}
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-600 resize-none text-gray-100"
              />
            </div>

            <div>
              <label className="text-xs text-gray-400 mb-1 block">Preferencias de respuesta</label>
              <textarea
                value={preferences}
                onChange={(e) => setPreferences(e.target.value)}
                placeholder="Ej: Prefiero respuestas técnicas y directas, con ejemplos de código cuando sea relevante..."
                rows={2}
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-600 resize-none text-gray-100"
              />
            </div>

            <div>
              <label className="text-xs text-gray-400 mb-1 block">Idioma de respuesta</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm outline-none focus:border-emerald-500 transition-colors text-gray-100"
              >
                <option value="es">🇦🇷 Español</option>
                <option value="en">🇺🇸 English</option>
                <option value="pt">🇧🇷 Português</option>
                <option value="fr">🇫🇷 Français</option>
                <option value="de">🇩🇪 Deutsch</option>
                <option value="it">🇮🇹 Italiano</option>
              </select>
            </div>
          </div>

          <button
            onClick={save}
            disabled={saving}
            className="w-full mt-6 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 text-white rounded-xl text-sm font-medium transition-colors flex items-center justify-center gap-2"
          >
            {saving ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Guardando...
              </>
            ) : saved ? (
              <>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                Guardado
              </>
            ) : (
              "Guardar perfil"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}