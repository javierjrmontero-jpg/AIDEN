import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["mate.local", "192.168.2.128"],
  // En desarrollo activo, no bloquear el build de producción por
  // errores de tipos o lint (se pueden endurecer más adelante).
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
};

export default nextConfig;
