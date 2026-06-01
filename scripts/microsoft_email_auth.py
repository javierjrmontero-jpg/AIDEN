#!/usr/bin/env python3
"""
Genera el refresh_token de Microsoft Graph para MATE (email Outlook/Hotmail).

Usa Device Code Flow: NO necesita redirect URI ni navegador en la misma máquina.
Podés ejecutarlo en tu PC o en la VM; el script imprime un código y una URL,
vos lo ingresás en https://microsoft.com/devicelogin desde cualquier navegador.

Requiere:
    pip install requests

Uso:
    set MICROSOFT_CLIENT_ID=...        (PowerShell: $env:MICROSOFT_CLIENT_ID="...")
    python microsoft_email_auth.py

Al final imprime el refresh_token, que se pega en MATE -> Email -> Conectar Outlook.
"""

import os
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("Falta requests. Instalá:  pip install requests")

CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID") or input("MICROSOFT_CLIENT_ID: ").strip()

# 'common' acepta cuentas personales y de organización. Para solo personales: 'consumers'.
AUTHORITY = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
SCOPE = "offline_access User.Read Mail.Read Mail.Send"

# 1) Solicitar device code
dc = requests.post(
    f"{AUTHORITY}/devicecode",
    data={"client_id": CLIENT_ID, "scope": SCOPE},
).json()

if "device_code" not in dc:
    sys.exit(f"Error al iniciar device flow: {dc}")

print("\n" + "=" * 64)
print(dc.get("message", "Andá a https://microsoft.com/devicelogin e ingresá el código."))
print("=" * 64 + "\n")

device_code = dc["device_code"]
interval = dc.get("interval", 5)

# 2) Poll hasta que el usuario autorice
while True:
    time.sleep(interval)
    tok = requests.post(
        f"{AUTHORITY}/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": CLIENT_ID,
            "device_code": device_code,
        },
    ).json()

    if "refresh_token" in tok:
        print("\n========== REFRESH TOKEN (pegalo en MATE) ==========")
        print(tok["refresh_token"])
        print("====================================================")
        break

    error = tok.get("error")
    if error == "authorization_pending":
        continue
    elif error == "slow_down":
        interval += 5
        continue
    else:
        sys.exit(f"Error: {tok.get('error_description', tok)}")
