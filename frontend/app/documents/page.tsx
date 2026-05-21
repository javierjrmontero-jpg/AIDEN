"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

const API_URL = "http://192.168.2.128:8000";

interface Document {
  id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  chunk_count: number;
  status: string;
  created_at: string;
}

export default function Documents() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const t = localStorage.getItem("mate_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    loadDocuments(t);
  }, [router]);

  const loadDocuments = async (t: string) => {
    const res = await fetch(`${API_URL}/api/v1/documents`, {
      headers: { "Authorization": `Bearer ${t}` }
    });
    const data = await res.json();
    setDocuments(data);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !token) return;

    setUploading(true);
    setError("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_URL}/api/v1/documents`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` },
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Error al subir el archivo");
        return;
      }
      loadDocuments(token);
    } catch {
      setError("Error de conexión");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const deleteDocument = async (id: string) => {
    if (!token) return;
    await fetch(`${API_URL}/api/v1/documents/${id}`, {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${token}` }
    });
    loadDocuments(token);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleDateString("es-AR", {
      day: "2-digit", month: "short", year: "numeric"
    });
  };

  const typeIcon = (type: string) => {
    const icons: Record<string, string> = {
      pdf: "📄", txt: "📝", docx: "📃", md: "📋"
    };
    return icons[type] || "📄";
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 px-4 py-8">
      <div className="max-w-2xl mx-auto">

        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <button
            onClick={() => router.push("/")}
            className="text-gray-500 hover:text-gray-300 transition-colors"
          >
            ← Volver
          </button>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="font-semibold">MATE</span>
          </div>
          <span className="text-xs text-gray-600 ml-auto">by JJRM</span>
        </div>

        <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 mb-4">
          <h2 className="text-lg font-semibold mb-1">Documentos</h2>
          <p className="text-xs text-gray-500 mb-6">
            MATE usa estos documentos para responder preguntas con contexto específico tuyo
          </p>

          {/* Upload area */}
          <div
            onClick={() => fileRef.current?.click()}
            className="border-2 border-dashed border-gray-700 hover:border-emerald-500 rounded-xl p-8 text-center cursor-pointer transition-colors mb-6"
          >
            <div className="text-3xl mb-2">📎</div>
            <p className="text-sm text-gray-400">
              {uploading ? "Procesando..." : "Clic para subir un documento"}
            </p>
            <p className="text-xs text-gray-600 mt-1">PDF, TXT, DOCX, MD — máximo 10 MB</p>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.txt,.docx,.md"
              onChange={handleUpload}
              className="hidden"
              disabled={uploading}
            />
          </div>

          {error && (
            <p className="text-red-400 text-xs mb-4 text-center">{error}</p>
          )}

          {/* Lista de documentos */}
          {documents.length === 0 ? (
            <p className="text-xs text-gray-600 text-center py-4">
              No hay documentos cargados aún
            </p>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center gap-3 bg-gray-800 rounded-xl px-4 py-3"
                >
                  <span className="text-xl">{typeIcon(doc.file_type)}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-200 truncate">{doc.filename}</p>
                    <p className="text-xs text-gray-500">
                      {formatSize(doc.size_bytes)} · {doc.chunk_count} fragmentos · {formatDate(doc.created_at)}
                    </p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    doc.status === "ready"
                      ? "bg-emerald-900 text-emerald-400"
                      : "bg-yellow-900 text-yellow-400"
                  }`}>
                    {doc.status === "ready" ? "✓ Listo" : "⏳ Procesando"}
                  </span>
                  <button
                    onClick={() => deleteDocument(doc.id)}
                    className="text-gray-600 hover:text-red-400 transition-colors text-sm ml-2"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <p className="text-xs text-gray-600 text-center">
          Los documentos se procesan localmente en tu servidor
        </p>
      </div>
    </div>
  );
}
