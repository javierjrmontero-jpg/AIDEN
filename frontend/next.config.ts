import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Orígenes permitidos en modo dev. En producción (next build + next start)
  // esta lista no tiene efecto. IPs activas: 192.168.135.129 (ens160),
  // 192.168.1.92 (ens224) — acceso habitual vía mate.local.
  allowedDevOrigins: ["mate.local", "192.168.135.129", "192.168.1.92"],
  // No bloquear el build de producción por errores de tipos.
  typescript: { ignoreBuildErrors: true },
};

export default nextConfig;
