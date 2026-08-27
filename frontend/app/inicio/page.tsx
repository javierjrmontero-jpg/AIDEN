import type { Metadata } from "next";
import Link from "next/link";

/**
 * Página pública de MATE.
 *
 * Google exige, para verificar una app que pide permisos sensibles, una
 * página principal accesible sin iniciar sesión, alojada en el mismo dominio
 * verificado, que describa la aplicación y enlace la política de privacidad.
 * La raíz del sitio no sirve para eso: redirige al login.
 */

export const metadata: Metadata = {
  title: "MATE — Motor de Asistencia Técnica e Inteligencia",
  description:
    "Asistente personal privado que corre sobre infraestructura propia: chat, documentos, agenda, tareas y voz.",
};

const CAPACIDADES = [
  {
    titulo: "Conversación con contexto",
    texto:
      "Un asistente que recuerda tus conversaciones anteriores y responde con el contexto de tus propios documentos, no con generalidades.",
  },
  {
    titulo: "Documentos propios",
    texto:
      "Subís PDFs, notas y manuales. MATE los indexa y los usa para responder preguntas sobre tu material específico.",
  },
  {
    titulo: "Agenda y tareas",
    texto:
      "Consulta tu calendario y crea eventos y recordatorios cuando se lo pedís en lenguaje natural.",
  },
  {
    titulo: "Voz",
    texto:
      "Una consola de escritorio que escucha, transcribe localmente y responde hablando, sin enviar tu audio a terceros.",
  },
];

export default function Inicio() {
  return (
    <main className="min-h-screen bg-[#080B0F] text-[#C6D3DE]">
      <div className="mx-auto max-w-3xl px-6 py-20">

        <header className="flex items-center gap-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/mate-logo.svg" alt="" width={56} height={56} />
          <div>
            <h1 className="text-2xl font-bold tracking-[0.14em] text-[#3FBFB0]">MATE</h1>
            <p className="text-xs uppercase tracking-[0.18em] text-[#45545F]">
              Motor de Asistencia Técnica e Inteligencia
            </p>
          </div>
        </header>

        <p className="mt-14 max-w-[62ch] text-lg leading-relaxed text-[#C6D3DE]">
          MATE es un asistente personal que corre sobre infraestructura propia.
          Tus conversaciones, documentos y credenciales viven en tu servidor, no
          en el de un proveedor.
        </p>

        <section className="mt-14 grid gap-px overflow-hidden rounded-lg bg-[#1D2833] sm:grid-cols-2">
          {CAPACIDADES.map((c) => (
            <article key={c.titulo} className="bg-[#0F151C] p-6">
              <h2 className="text-sm font-semibold tracking-wide text-[#C6D3DE]">{c.titulo}</h2>
              <p className="mt-2 text-sm leading-relaxed text-[#6E8090]">{c.texto}</p>
            </article>
          ))}
        </section>

        <section className="mt-14 border-t border-[#1D2833] pt-10">
          <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-[#6E8090]">
            Sobre el acceso a tu cuenta de Google
          </h2>
          <p className="mt-4 max-w-[62ch] text-sm leading-relaxed text-[#6E8090]">
            Si conectás tu calendario, MATE pide permiso para ver y crear eventos
            en tu Google Calendar. Ese permiso se usa únicamente para mostrarte tu
            agenda dentro de la aplicación y para crear los eventos que vos le
            pedís. No se comparte con terceros ni se usa para publicidad ni para
            entrenar modelos. Podés revocarlo cuando quieras.
          </p>
          <Link
            href="/privacidad"
            className="mt-6 inline-block border border-[#2A3946] px-4 py-2 text-sm text-[#3FBFB0] transition-colors hover:border-[#3FBFB0]"
          >
            Política de privacidad
          </Link>
        </section>

        <footer className="mt-20 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-[#1D2833] pt-8 text-xs text-[#45545F]">
          <span>MATE — by JJRM</span>
          <Link href="/privacidad" className="hover:text-[#6E8090]">Privacidad</Link>
          <Link href="/login" className="hover:text-[#6E8090]">Ingresar</Link>
        </footer>

      </div>
    </main>
  );
}
