"use client";

import { useState, useRef } from "react";

interface Props {
  onTranscript: (text: string) => void;
  disabled?: boolean;
  language?: string;
}

export default function VoiceInput({ onTranscript, disabled, language = "es-AR" }: Props) {
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const sendAudio = async (blob: Blob) => {
    const token = localStorage.getItem("mate_token");
    if (!token) return;
    setTranscribing(true);
    try {
      const fd = new FormData();
      fd.append("file", blob, "audio.webm");
      fd.append("language", language);
      const res = await fetch("/api/v1/transcribe", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }, // NO setear Content-Type: el browser pone el boundary
        body: fd,
      });
      if (res.ok) {
        const data = await res.json();
        if (data.text) onTranscript(data.text);
      } else {
        console.error("Transcribe HTTP", res.status);
      }
    } catch (e) {
      console.error("Transcribe error:", e);
    } finally {
      setTranscribing(false);
    }
  };

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];
      const mr = new MediaRecorder(stream);
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        await sendAudio(blob);
      };
      mr.start();
      mediaRecorderRef.current = mr;
      setRecording(true);
    } catch (e) {
      console.error("Mic error:", e);
      alert("No se pudo acceder al micrófono. Revisá los permisos del navegador.");
    }
  };

  const stop = () => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  };

  const toggle = () => {
    if (transcribing) return;
    if (recording) stop();
    else start();
  };

  return (
    <button
      onClick={toggle}
      disabled={disabled || transcribing}
      title={recording ? "Detener y transcribir" : transcribing ? "Transcribiendo..." : "Hablar"}
      className={`p-3 rounded-xl transition-all ${
        recording
          ? "bg-red-600 hover:bg-red-500 animate-pulse"
          : "bg-gray-700 hover:bg-gray-600"
      } disabled:opacity-50`}
    >
      {transcribing ? (
        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
      ) : recording ? (
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <rect x="6" y="6" width="12" height="12" rx="2" />
        </svg>
      ) : (
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>
      )}
    </button>
  );
}
