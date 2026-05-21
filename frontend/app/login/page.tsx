"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = "http://192.168.2.128:8000";

export default function Login() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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

    } catch (e) {
      setError("No se pudo conectar con MATE");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSubmit();
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
        </div>
      </div>
    </div>
  );
}
