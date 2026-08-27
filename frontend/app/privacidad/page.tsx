import type { Metadata } from "next";
import Link from "next/link";

/**
 * Política de privacidad.
 *
 * Debe cubrir lo que exige la Política de Datos de Usuario de los Servicios de
 * API de Google: qué datos se acceden, con qué fin, cómo se almacenan, con
 * quién se comparten, cuánto se conservan, cómo se eliminan, y la declaración
 * de Uso Limitado. Sin esos puntos, la verificación se rechaza.
 */

export const metadata: Metadata = {
  title: "Política de privacidad — MATE",
  description:
    "Qué datos usa MATE, con qué fin, dónde se almacenan y cómo eliminarlos.",
};

const ACTUALIZADO = "26 de agosto de 2026";

function Seccion({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="mt-12">
      <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-[#3FBFB0]">
        {titulo}
      </h2>
      <div className="mt-4 space-y-4 text-sm leading-relaxed text-[#8fa0ad]">{children}</div>
    </section>
  );
}

export default function Privacidad() {
  return (
    <main className="min-h-screen bg-[#080B0F] text-[#C6D3DE]">
      <div className="mx-auto max-w-2xl px-6 py-20">

        <Link href="/inicio" className="text-xs text-[#45545F] hover:text-[#6E8090]">
          ← MATE
        </Link>

        <h1 className="mt-8 text-3xl font-bold tracking-tight text-[#C6D3DE]">
          Política de privacidad
        </h1>
        <p className="mt-3 text-xs uppercase tracking-[0.14em] text-[#45545F]">
          Última actualización: {ACTUALIZADO}
        </p>

        <p className="mt-10 max-w-[65ch] text-sm leading-relaxed text-[#8fa0ad]">
          MATE (Motor de Asistencia Técnica e Inteligencia) es un asistente
          personal operado de forma privada por JJRM. Esta política describe qué
          datos trata la aplicación, con qué finalidad y durante cuánto tiempo.
        </p>

        <Seccion titulo="Quién opera esta aplicación">
          <p>
            MATE es operado de forma individual y privada por JJRM. No es un
            servicio comercial, no tiene usuarios anónimos y el acceso está
            restringido a cuentas autorizadas expresamente por el administrador.
            Consultas: <span className="text-[#C6D3DE]">javierjrmontero@gmail.com</span>
          </p>
        </Seccion>

        <Seccion titulo="Qué datos tratamos">
          <p>Al usar MATE se almacenan, según las funciones que actives:</p>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong className="text-[#C6D3DE]">Cuenta:</strong> tu dirección de
              correo y tu nombre, para identificarte al iniciar sesión.
            </li>
            <li>
              <strong className="text-[#C6D3DE]">Conversaciones:</strong> los
              mensajes que intercambiás con el asistente.
            </li>
            <li>
              <strong className="text-[#C6D3DE]">Documentos:</strong> los archivos
              que subas voluntariamente y el texto extraído de ellos.
            </li>
            <li>
              <strong className="text-[#C6D3DE]">Datos de Google:</strong> si
              conectás tu calendario, los eventos de tu Google Calendar y la
              dirección de correo de esa cuenta.
            </li>
          </ul>
        </Seccion>

        <Seccion titulo="Uso de los datos de tu cuenta de Google">
          <p>
            MATE solicita el permiso{" "}
            <code className="text-[#3FBFB0]">
              https://www.googleapis.com/auth/calendar
            </code>{" "}
            con dos fines, y ninguno más:
          </p>
          <ul className="list-disc space-y-2 pl-5">
            <li>Mostrarte tus próximos eventos dentro de la aplicación.</li>
            <li>Crear eventos en tu calendario cuando se lo pedís explícitamente.</li>
          </ul>
          <p>
            Se solicita el permiso de acceso completo y no el de solo lectura
            porque la aplicación necesita crear eventos, además de leerlos.
          </p>
          <p className="border-l-2 border-[#2A3946] pl-4 text-[#C6D3DE]">
            El uso que MATE hace de la información recibida de las API de Google
            se ajusta a la{" "}
            <a
              href="https://developers.google.com/terms/api-services-user-data-policy"
              className="text-[#3FBFB0] underline underline-offset-2"
              target="_blank"
              rel="noopener noreferrer"
            >
              Política de Datos de Usuario de los Servicios de API de Google
            </a>
            , incluidos los requisitos de Uso Limitado.
          </p>
        </Seccion>

        <Seccion titulo="Qué NO hacemos con tus datos">
          <ul className="list-disc space-y-2 pl-5">
            <li>No los vendemos ni los cedemos a terceros.</li>
            <li>No los usamos para publicidad ni para elaborar perfiles.</li>
            <li>No los usamos para entrenar modelos de inteligencia artificial.</li>
            <li>
              No permitimos que personas los lean, salvo que vos lo pidas
              expresamente para resolver un problema técnico, o que la ley lo exija.
            </li>
          </ul>
        </Seccion>

        <Seccion titulo="Dónde se almacenan">
          <p>
            Todos los datos residen en un servidor privado operado por JJRM en
            Argentina. Las credenciales de acceso a servicios externos, incluido
            el token de tu calendario, se guardan en ese mismo servidor y nunca
            se envían al navegador.
          </p>
          <p>
            Para generar las respuestas del asistente, el contenido de la
            conversación se envía a la API de Anthropic, que lo procesa
            únicamente para producir la respuesta. Los eventos de tu calendario
            solo se incluyen en ese envío si tu consulta se refiere a tu agenda.
          </p>
        </Seccion>

        <Seccion titulo="Cuánto se conservan y cómo eliminarlos">
          <p>
            Los datos se conservan mientras tu cuenta exista. Podés eliminarlos en
            cualquier momento:
          </p>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong className="text-[#C6D3DE]">Calendario:</strong> desde
              Calendario → Conexión → Desconectar. Eso borra el token de acceso
              del servidor de forma inmediata.
            </li>
            <li>
              <strong className="text-[#C6D3DE]">Documentos y conversaciones:</strong>{" "}
              desde sus respectivas pantallas dentro de la aplicación.
            </li>
            <li>
              <strong className="text-[#C6D3DE]">Cuenta completa:</strong>{" "}
              escribiendo a la dirección de contacto; se elimina en un plazo
              máximo de 30 días.
            </li>
          </ul>
          <p>
            También podés revocar el acceso de MATE a tu cuenta de Google en
            cualquier momento desde{" "}
            <a
              href="https://myaccount.google.com/permissions"
              className="text-[#3FBFB0] underline underline-offset-2"
              target="_blank"
              rel="noopener noreferrer"
            >
              myaccount.google.com/permissions
            </a>
            , sin pasar por la aplicación.
          </p>
        </Seccion>

        <Seccion titulo="Seguridad">
          <p>
            El acceso a la aplicación exige autenticación, con verificación en dos
            pasos disponible. Todo el tráfico viaja cifrado por HTTPS. Las
            contraseñas se almacenan con hash y nunca en texto plano. Las cuentas
            nuevas requieren aprobación explícita del administrador antes de poder
            ingresar.
          </p>
        </Seccion>

        <Seccion titulo="Cambios">
          <p>
            Si esta política cambia, se actualiza la fecha del encabezado. Los
            cambios que afecten el uso de datos de Google se comunicarán a los
            usuarios activos antes de aplicarse.
          </p>
        </Seccion>

        <footer className="mt-16 border-t border-[#1D2833] pt-8 text-xs text-[#45545F]">
          MATE — by JJRM · <Link href="/inicio" className="hover:text-[#6E8090]">Inicio</Link>
        </footer>

      </div>
    </main>
  );
}
