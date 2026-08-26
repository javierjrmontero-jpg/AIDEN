#!/usr/bin/env python3
"""
Genera el refresh_token de Google Calendar para MATE.

Abre el navegador de esta máquina, te pide autorizar la cuenta, y al final
imprime el refresh_token. Ese valor se pega en MATE -> Calendario -> Conexión.

Requiere:
    pip install google-auth-oauthlib

Uso (PowerShell):
    $env:GOOGLE_CLIENT_ID="...apps.googleusercontent.com"
    $env:GOOGLE_CLIENT_SECRET="..."
    python scripts/google_calendar_auth.py

Las credenciales son las mismas que tiene el backend en su .env. En Google
Cloud Console, el cliente OAuth debe ser de tipo "Aplicación de escritorio":
ese tipo acepta el redirect a localhost que usa este script.

El refresh_token solo se entrega la primera vez que autorizás la app. Si el
script termina sin imprimirlo, revocá el acceso en
https://myaccount.google.com/permissions y volvé a ejecutarlo.
"""

import os
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    sys.exit("Falta la dependencia. Instalá:  pip install google-auth-oauthlib")

# Debe coincidir con SCOPES en backend/app/services/calendar/service.py
SCOPES = ["https://www.googleapis.com/auth/calendar"]

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID") or input("GOOGLE_CLIENT_ID: ").strip()
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET") or input("GOOGLE_CLIENT_SECRET: ").strip()

if not CLIENT_ID or not CLIENT_SECRET:
    sys.exit("Faltan GOOGLE_CLIENT_ID y/o GOOGLE_CLIENT_SECRET.")

config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

flow = InstalledAppFlow.from_client_config(config, SCOPES)

print("\nSe va a abrir el navegador para autorizar el acceso al calendario.")
print("Elegí la cuenta que querés conectar a MATE.\n")

# prompt="consent" fuerza la pantalla de permisos: sin eso Google no vuelve a
# emitir refresh_token si la cuenta ya autorizó esta app antes.
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

if not creds.refresh_token:
    sys.exit(
        "\nGoogle no devolvió refresh_token.\n"
        "Revocá el acceso de MATE en https://myaccount.google.com/permissions "
        "y volvé a ejecutar este script."
    )

print("\n" + "=" * 70)
print("REFRESH TOKEN — pegalo en MATE -> Calendario -> Conexión:")
print("=" * 70)
print(creds.refresh_token)
print("=" * 70)
print("\nNo lo compartas: da acceso a tu calendario.\n")
