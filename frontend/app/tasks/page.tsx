"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useGoBack } from "@/components/useGoBack";

interface Task {
  id: string;
  title: string;
  description: string;
  due_date: string | null;
  priority: "low" | "medium" | "high";
  completed: boolean;
  created_at: string;
}

export default function Tasks() {
  const router = useRouter();
  const goBack = useGoBack();
  const [token, setToken] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [filter, setFilter] = useState<"all" | "pending" | "completed">("pending");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [priority, setPriority] = useState("medium");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("mate_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    loadTasks(t);
  }, [router]);

  const loadTasks = async (t: string) => {
    setLoading(true);
    try {
      const url = filter === "all" ? "/api/v1/tasks" :
                  filter === "pending" ? "/api/v1/tasks?completed=false" :
                  "/api/v1/tasks?completed=true";
      const res = await fetch(url, { headers: { "Authorization": `Bearer ${t}` } });
      setTasks(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (token) loadTasks(token);
  }, [filter, token]);

  const createTask = async () => {
    if (!title.trim() || !token) return;
    setSaving(true);
    try {
      await fetch("/api/v1/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ title, description, due_date: dueDate || null, priority })
      });
      setTitle(""); setDescription(""); setDueDate(""); setPriority("medium");
      setShowForm(false);
      loadTasks(token);
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const toggleComplete = async (task: Task) => {
    if (!token) return;
    await fetch(`/api/v1/tasks/${task.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
      body: JSON.stringify({ completed: !task.completed })
    });
    loadTasks(token);
  };

  const deleteTask = async (id: string) => {
    if (!token) return;
    await fetch(`/api/v1/tasks/${id}`, {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${token}` }
    });
    loadTasks(token);
  };

  const priorityConfig = {
    high: { label: "Alta", color: "text-red-400", bg: "bg-red-900/30", icon: "🔴" },
    medium: { label: "Media", color: "text-yellow-400", bg: "bg-yellow-900/30", icon: "🟡" },
    low: { label: "Baja", color: "text-green-400", bg: "bg-green-900/30", icon: "🟢" },
  };

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "numeric" });

  const isOverdue = (due: string | null) =>
    due && new Date(due) < new Date() ? true : false;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 px-4 py-8">
      <div className="max-w-2xl mx-auto">

        <div className="flex items-center gap-3 mb-8">
          <button onClick={() => goBack()}
            className="p-2 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </button>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="font-semibold">MATE</span>
          </div>
          <span className="text-sm text-gray-500 ml-1">Tareas</span>
          <span className="text-xs text-gray-600 ml-auto">by JJRM</span>
        </div>

        {/* Filtros y botón nueva tarea */}
        <div className="flex items-center gap-2 mb-4">
          {(["pending", "all", "completed"] as const).map((f) => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                filter === f ? "bg-emerald-600 text-white" : "bg-gray-800 text-gray-400 hover:text-gray-200"
              }`}>
              {f === "pending" ? "Pendientes" : f === "completed" ? "Completadas" : "Todas"}
            </button>
          ))}
          <button onClick={() => setShowForm(!showForm)}
            className="ml-auto flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-xs font-medium transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            Nueva tarea
          </button>
        </div>

        {/* Formulario nueva tarea */}
        {showForm && (
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 mb-4">
            <h3 className="text-sm font-semibold mb-3">Nueva tarea</h3>
            <div className="space-y-3">
              <input type="text" placeholder="Título de la tarea *" value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-600 text-gray-100" />
              <textarea placeholder="Descripción (opcional)" value={description}
                onChange={(e) => setDescription(e.target.value)} rows={2}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 transition-colors placeholder-gray-600 resize-none text-gray-100" />
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Fecha límite</label>
                  <input type="datetime-local" value={dueDate}
                    onChange={(e) => setDueDate(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 transition-colors text-gray-100" />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Prioridad</label>
                  <select value={priority} onChange={(e) => setPriority(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 transition-colors text-gray-100">
                    <option value="high">🔴 Alta</option>
                    <option value="medium">🟡 Media</option>
                    <option value="low">🟢 Baja</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <button onClick={() => setShowForm(false)}
                  className="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs transition-colors">
                  Cancelar
                </button>
                <button onClick={createTask} disabled={saving || !title.trim()}
                  className="px-3 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 rounded-lg text-xs font-medium transition-colors">
                  {saving ? "Guardando..." : "Crear tarea"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Lista de tareas */}
        <div className="space-y-2">
          {loading ? (
            <p className="text-center text-gray-600 py-8">Cargando...</p>
          ) : tasks.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-600 text-sm">No hay tareas {filter === "pending" ? "pendientes" : filter === "completed" ? "completadas" : ""}</p>
              <button onClick={() => setShowForm(true)}
                className="mt-3 text-xs text-emerald-500 hover:text-emerald-400 transition-colors">
                + Crear primera tarea
              </button>
            </div>
          ) : (
            tasks.map((task) => (
              <div key={task.id}
                className={`flex items-start gap-3 bg-gray-900 rounded-xl px-4 py-3 border transition-colors ${
                  task.completed ? "border-gray-800 opacity-60" : "border-gray-800 hover:border-gray-700"
                }`}>
                <button onClick={() => toggleComplete(task)}
                  className={`mt-0.5 w-5 h-5 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
                    task.completed ? "bg-emerald-600 border-emerald-600" : "border-gray-600 hover:border-emerald-500"
                  }`}>
                  {task.completed && (
                    <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  )}
                </button>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm ${task.completed ? "line-through text-gray-500" : "text-gray-200"}`}>
                    {task.title}
                  </p>
                  {task.description && (
                    <p className="text-xs text-gray-500 mt-0.5">{task.description}</p>
                  )}
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${priorityConfig[task.priority].bg} ${priorityConfig[task.priority].color}`}>
                      {priorityConfig[task.priority].icon} {priorityConfig[task.priority].label}
                    </span>
                    {task.due_date && (
                      <span className={`text-xs ${isOverdue(task.due_date) && !task.completed ? "text-red-400" : "text-gray-500"}`}>
                        {isOverdue(task.due_date) && !task.completed ? "⚠️ " : "📅 "}
                        {formatDate(task.due_date)}
                      </span>
                    )}
                  </div>
                </div>
                <button onClick={() => deleteTask(task.id)}
                  className="p-1 rounded hover:bg-red-900 text-gray-600 hover:text-red-400 transition-colors flex-shrink-0">
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                    <path d="M10 11v6M14 11v6"/>
                    <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                  </svg>
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}