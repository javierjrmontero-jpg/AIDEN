"use client";

import { useCallback, useRef } from "react";

export function useTTS(language: string = "es-AR") {
  const speaking = useRef(false);

  const speak = useCallback((text: string) => {
    if (!window.speechSynthesis) return;

    // Limpiar markdown básico para la voz
    const clean = text
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/\*(.*?)\*/g, "$1")
      .replace(/#{1,6}\s/g, "")
      .replace(/`{1,3}(.*?)`{1,3}/g, "$1")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/\n+/g, ". ")
      .trim();

    if (!clean) return;

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.lang = language;
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    // Buscar voz en el idioma preferido
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(v => v.lang.startsWith(language.split("-")[0]));
    if (preferred) utterance.voice = preferred;

    utterance.onstart = () => { speaking.current = true; };
    utterance.onend = () => { speaking.current = false; };

    window.speechSynthesis.speak(utterance);
  }, [language]);

  const stop = useCallback(() => {
    window.speechSynthesis?.cancel();
    speaking.current = false;
  }, []);

  return { speak, stop };
}