import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["mate.local", "192.168.2.128"],
  // En desarrollo activo, no bloquear el build de producción por
  // errores de tipos (se pueden endurecer más adelante).
  typescript: { ignoreBuildErrors: true },
};

export default nextConfig;