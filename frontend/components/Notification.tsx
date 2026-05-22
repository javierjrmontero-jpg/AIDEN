"use client";

import { useEffect, useState } from "react";

interface NotificationProps {
  message: string;
  type: "info" | "warning" | "error" | "success";
  onClose: () => void;
  duration?: number;
}

export default function Notification({ message, type, onClose, duration = 5000 }: NotificationProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, duration);
    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const styles = {
    info: "bg-blue-900 border-blue-700 text-blue-200",
    warning: "bg-yellow-900 border-yellow-700 text-yellow-200",
    error: "bg-red-900 border-red-700 text-red-200",
    success: "bg-emerald-900 border-emerald-700 text-emerald-200",
  };

  const icons = {
    info: "ℹ️",
    warning: "⚠️",
    error: "❌",
    success: "✓",
  };

  return (
    <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl border text-sm shadow-lg ${styles[type]} animate-fade-in`}>
      <span>{icons[type]}</span>
      <span>{message}</span>
      <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100 transition-opacity">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
  );
}