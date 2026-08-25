"use client";

import { useRouter } from "next/navigation";

/**
 * Vuelve a la pantalla anterior en lugar de saltar siempre al inicio.
 * Si la pestaña se abrió directamente en esta ruta no hay historial propio
 * al que volver, así que cae al inicio.
 */
export function useGoBack() {
  const router = useRouter();
  return () => {
    if (typeof window !== "undefined" && window.history.length > 1) router.back();
    else router.push("/");
  };
}
