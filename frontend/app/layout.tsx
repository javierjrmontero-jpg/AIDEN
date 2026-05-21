import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MATE — by JJRM",
  description: "Motor de Asistencia Técnica e Inteligencia",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="antialiased">{children}</body>
    </html>
  );
}
