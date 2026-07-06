"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";

const API_URL = "";

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Handle Google OAuth callback: /login?token=...&name=...&email=...
  useEffect(() => {
    const token = searchParams.get("token");
    const oauthName = searchParams.get("name");
    const oauthEmail = searchParams.get("email");
    const oauthError = searchParams.get("error");

    if (oauthError) {
      const msgs: Record<string, string> = {
        google_denied: "Acceso con Google cancelado",
        state_mismatch: "Error de seguridad en OAuth. Intentá de nuevo",
        token_exchange: "Error al comunicarse con Google",
        userinfo: "No se pudo obtener información de tu cuenta",
        no_email: "Google no devolvió un email válido",
      };
      setError(msgs[oauthError] || "Error al iniciar sesión con Google");
      return;
    }

    if (token && oauthName && oauthEmail) {
      localStorage.setItem("mate_token", token);
      localStorage.setItem("mate_user", JSON.stringify({ name: oauthName, email: oauthEmail }));
      router.push("/");
    }
  }, [searchParams, router]);

  const handleSubmit = async () => {
    if (!email || !password || (mode === "register" && !name)) {
      setError("Completá todos los campos");
      return;
    }
    setLoading(true);
    setError("");

    try {
      const endpoint = mode === "login" ? "/api/v1/auth/login" : "/api/v1/auth/register";
      const body = mode === "login"
        ? { email, password }
        : { email, name, password };

      const res = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || "Error al autenticar");
        return;
      }

      localStorage.setItem("mate_token", data.token);
      localStorage.setItem("mate_user", JSON.stringify({ name: data.name, email: data.email }));
      router.push("/");

    } catch {
      setError("No se pudo conectar con MATE");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSubmit();
  };

  const handleGoogleLogin = () => {
    window.location.href = `${API_URL}/api/v1/auth/google`;
  };

  return (
    <div className="flex items-center justify-center h-screen bg-gray-950 text-gray-100">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <h1 className="text-2xl font-bold tracking-wide">MATE</h1>
          </div>
          <p className="text-xs text-gray-500">Motor de Asistencia Técnica e Inteligencia</p>
          <p className="text-xs text-gray-600 mt-1">by JJRM</p>
        </div>

        {/* Card */}
        <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
          {/* Tabs */}
          <div className="flex rounded-lg bg-gray-800 p-1 mb-6">
            <button
              onClick={() => { setMode("login"); setError(""); }}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === "login" ? "bg-emerald-600 text-white" : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Ingresar
            </button>
            <button
              onClick={() => { setMode("register"); setError(""); }}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === "register" ? "bg-emerald-600 text-white" : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Registrarse
            </button>
          </div>

          {/* Fields */}
          <div className="space-y-3">
            {mode === "register" && (
              <input
                type="text"
                placeholder="Tu nombre"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-500"
              />
            )}
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-500"
            />
            <input
              type="password"
              placeholder="Contraseña"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-500"
            />
          </div>

          {error && (
            <p className="text-red-400 text-xs mt-3 text-center">{error}</p>
          )}

          <button
            onClick={handleSubmit}
            disabled={loading}
            className="w-full mt-4 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl text-sm font-medium transition-colors"
          >
            {loading ? "..." : mode === "login" ? "Ingresar" : "Crear cuenta"}
          </button>

          {/* Divider */}
          <div className="flex items-center gap-3 my-4">
            <div className="flex-1 h-px bg-gray-700" />
            <span className="text-xs text-gray-600">o</span>
            <div className="flex-1 h-px bg-gray-700" />
          </div>

          {/* Google OAuth */}
          <button
            onClick={handleGoogleLogin}
            className="w-full py-3 bg-white hover:bg-gray-100 text-gray-800 rounded-xl text-sm font-medium transition-colors flex items-center justify-center gap-2"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Continuar con Google
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Login() {
  return (
    <Suspense>
      <LoginContent />
    </Suspense>
  );
}
