"use client";

import { useState, useCallback } from "react";

interface NotificationState {
  id: string;
  message: string;
  type: "info" | "warning" | "error" | "success";
}

export function useNotifications() {
  const [notifications, setNotifications] = useState<NotificationState[]>([]);

  const notify = useCallback((message: string, type: "info" | "warning" | "error" | "success" = "info") => {
    const id = Math.random().toString(36).slice(2);
    setNotifications(prev => [...prev, { id, message, type }]);
    return id;
  }, []);

  const dismiss = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  return { notifications, notify, dismiss };
}