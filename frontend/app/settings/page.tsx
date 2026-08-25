"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useGoBack } from "@/components/useGoBack";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

function passwordStrength(pwd: string): { score: number; label: string; color: string; hints: string[] } {
  const hints: string[] = [];
  if (pwd.length < 8)        hints.push("mínimo 8 caracteres");
  if (!/[A-Z]/.test(pwd))   hints.push("una mayúscula");
  if (!/[a-z]/.test(pwd))   hints.push("una minúscula");
  if (!/\d/.test(pwd))      hints.push("un número");
  if (!/[!@#$%^&*()_+\-=\[\]{}|;':",.<>?/`~\\]/.test(pwd)) hints.push("un carácter especial");

  const score = 5 - hints.length;
  const labels = ["", "Muy débil", "Débil", "Regular", "Fuerte", "Muy fuerte"];
  const colors = ["", "bg-red-500", "bg-orange-500", "bg-yellow-500", "bg-blue-500", "bg-green-500"];
  return { score, label: pwd ? labels[score] : "", color: pwd ? colors[score] : "", hints };
}

export default function SettingsPage() {
  const router = useRouter();
  const goBack = useGoBack();
  const [token, setToken] = useState<string | null>(null);
  const [assistantName, setAssistantName] = useState("MATE");
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  // Password change state
  const [currentPwd, setCurrentPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [pwdError, setPwdError] = useState("");
  const [pwdSuccess, setPwdSuccess] = useState(false);
  const [pwdLoading, setPwdLoading] = useState(false);

  const strength = passwordStrength(newPwd);

  useEffect(() => {
    const t = localStorage.getItem("mate_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    fetch(`${API_URL}/api/v1/settings`, { headers: { Authorization: `Bearer ${t}` } })
      .then(r => r.json())
      .then(d => { if (d.assistant_name) setAssistantName(d.assistant_name); })
      .catch(() => {});
  }, [router]);

  const save = async () => {
    if (!token) return;
    setLoading(true);
    try {
      await fetch(`${API_URL}/api/v1/settings`, {
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

  const changePassword = async () => {
    setPwdError("");
    if (!currentPwd || !newPwd || !confirmPwd) {
      setPwdError("Completá todos los campos"); return;
    }
    if (newPwd !== confirmPwd) {
      setPwdError("Las contraseñas nuevas no coinciden"); return;
    }
    if (strength.score < 5) {
      setPwdError("La contraseña no cumple los requisitos: " + strength.hints.join(", ")); return;
    }
    setPwdLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/password`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ current_password: currentPwd, new_password: newPwd }),
      });
      if (!res.ok) {
        const err = await res.json();
        setPwdError(err.detail || "Error al cambiar la contraseña");
        return;
      }
      setPwdSuccess(true);
      setCurrentPwd(""); setNewPwd(""); setConfirmPwd("");
      setTimeout(() => setPwdSuccess(false), 3000);
    } catch {
      setPwdError("Error de conexión");
    } finally {
      setPwdLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col items-center justify-start px-4 py-10 gap-6">

      {/* Configuración general */}
      <div className="w-full max-w-md bg-gray-900 border border-gray-800 rounded-2xl p-8 space-y-6">
        <div className="flex items-center gap-3">
          <button onClick={() => goBack()}
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
          <p className="text-xs text-gray-600">Este nombre aparece en la UI, en el sistema y en la voz.</p>
        </div>

        <button onClick={save} disabled={loading}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-xl text-sm font-medium transition-colors">
          {loading ? "Guardando..." : saved ? "✓ Guardado" : "Guardar"}
        </button>
      </div>

      {/* Cambio de contraseña */}
      <div className="w-full max-w-md bg-gray-900 border border-gray-800 rounded-2xl p-8 space-y-5">
        <h2 className="text-lg font-semibold text-blue-400">Cambiar contraseña</h2>

        <div className="space-y-2">
          <label className="text-xs text-gray-400">Contraseña actual</label>
          <input
            type="password"
            value={currentPwd}
            onChange={e => setCurrentPwd(e.target.value)}
            placeholder="••••••••"
            className="w-full bg-gray-800 border border-gray-700 focus:border-blue-400 rounded-xl px-4 py-3 text-sm outline-none transition-colors text-gray-100 placeholder-gray-600"
          />
        </div>

        <div className="space-y-2">
          <label className="text-xs text-gray-400">Nueva contraseña</label>
          <input
            type="password"
            value={newPwd}
            onChange={e => setNewPwd(e.target.value)}
            placeholder="••••••••"
            className="w-full bg-gray-800 border border-gray-700 focus:border-blue-400 rounded-xl px-4 py-3 text-sm outline-none transition-colors text-gray-100 placeholder-gray-600"
          />

          {/* Barra de fortaleza */}
          {newPwd && (
            <div className="space-y-1">
              <div className="flex gap-1">
                {[1,2,3,4,5].map(i => (
                  <div key={i}
                    className={`h-1.5 flex-1 rounded-full transition-colors ${i <= strength.score ? strength.color : "bg-gray-700"}`}
                  />
                ))}
              </div>
              <p className={`text-xs ${strength.score >= 4 ? "text-green-400" : strength.score >= 3 ? "text-yellow-400" : "text-red-400"}`}>
                {strength.label}
              </p>
              {strength.hints.length > 0 && (
                <p className="text-xs text-gray-500">Falta: {strength.hints.join(", ")}</p>
              )}
            </div>
          )}
        </div>

        <div className="space-y-2">
          <label className="text-xs text-gray-400">Confirmar nueva contraseña</label>
          <input
            type="password"
            value={confirmPwd}
            onChange={e => setConfirmPwd(e.target.value)}
            placeholder="••••••••"
            className={`w-full bg-gray-800 border rounded-xl px-4 py-3 text-sm outline-none transition-colors text-gray-100 placeholder-gray-600 ${
              confirmPwd && confirmPwd !== newPwd ? "border-red-500" : "border-gray-700 focus:border-blue-400"
            }`}
          />
          {confirmPwd && confirmPwd !== newPwd && (
            <p className="text-xs text-red-400">Las contraseñas no coinciden</p>
          )}
        </div>

        {pwdError && <p className="text-xs text-red-400 bg-red-950 border border-red-800 rounded-lg px-3 py-2">{pwdError}</p>}
        {pwdSuccess && <p className="text-xs text-green-400 bg-green-950 border border-green-800 rounded-lg px-3 py-2">✓ Contraseña actualizada correctamente</p>}

        <button
          onClick={changePassword}
          disabled={pwdLoading || strength.score < 5 || newPwd !== confirmPwd || !currentPwd}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl text-sm font-medium transition-colors"
        >
          {pwdLoading ? "Actualizando..." : "Cambiar contraseña"}
        </button>

        <div className="text-xs text-gray-600 space-y-0.5 border-t border-gray-800 pt-4">
          <p className="font-medium text-gray-500 mb-1">Requisitos de seguridad:</p>
          <p>• Mínimo 8 caracteres</p>
          <p>• Al menos una mayúscula y una minúscula</p>
          <p>• Al menos un número</p>
          <p>• Al menos un carácter especial (!@#$%...)</p>
        </div>
      </div>

    </div>
  );
}
