"""
Domótica service for MATE backend.
Wraps the three platform adapters (Home Assistant, eWeLink, Tuya)
behind a unified async interface used by the API router.
"""
import os
import json
import asyncio
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Device:
    id:       str
    name:     str
    type:     str
    state:    dict = field(default_factory=dict)
    platform: str = ""

    @property
    def is_on(self) -> bool:
        return bool(self.state.get("on") or self.state.get("state") == "on")

    @property
    def friendly_state(self) -> str:
        if self.type == "sensor":
            v = self.state.get("value", "")
            u = self.state.get("unit", "")
            return f"{v} {u}".strip()
        return "encendido" if self.is_on else "apagado"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "type": self.type,
            "state": self.state, "platform": self.platform,
            "is_on": self.is_on, "friendly_state": self.friendly_state,
        }


# ─── Home Assistant ───────────────────────────────────────────────────────────

async def _ha_get_devices(client: httpx.AsyncClient) -> list[Device]:
    url   = os.environ.get("HA_URL", "").rstrip("/")
    token = os.environ.get("HA_TOKEN", "")
    if not url or not token:
        return []
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        r = await client.get(f"{url}/api/states", headers=headers, timeout=8)
        r.raise_for_status()
        skip = ("automation.", "input_", "person.", "zone.", "sun.", "weather.",
                "conversation.", "tts.", "todo.", "event.", "update.", "sensor.backup")
        devices = []
        for s in r.json():
            eid = s["entity_id"]
            if any(eid.startswith(p) for p in skip):
                continue
            domain = eid.split(".")[0]
            dtype = {"light": "light", "switch": "switch", "sensor": "sensor",
                     "binary_sensor": "sensor", "scene": "scene",
                     "climate": "climate", "cover": "cover", "fan": "switch"}.get(domain, "switch")
            attrs = s.get("attributes", {})
            sv = s.get("state", "off")
            dstate = {"state": sv, "on": sv == "on"}
            if dtype == "sensor":
                dstate = {"value": sv, "unit": attrs.get("unit_of_measurement", "")}
            elif dtype == "light":
                dstate["brightness"] = attrs.get("brightness")
            devices.append(Device(id=eid, name=attrs.get("friendly_name", eid),
                                  type=dtype, state=dstate, platform="ha"))
        return devices
    except Exception as e:
        logger.warning(f"HA get_devices: {e}")
        return []


async def _ha_control(client: httpx.AsyncClient, entity_id: str, action: str, params: dict = None) -> str:
    url   = os.environ.get("HA_URL", "").rstrip("/")
    token = os.environ.get("HA_TOKEN", "")
    if not url or not token:
        return "Home Assistant no configurado."
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    domain = entity_id.split(".")[0]
    service = {"on": f"{domain}/turn_on", "off": f"{domain}/turn_off",
               "toggle": f"{domain}/toggle", "scene": "scene/turn_on"}.get(action, f"{domain}/{action}")
    data = {"entity_id": entity_id, **(params or {})}
    try:
        await client.post(f"{url}/api/services/{service}", headers=headers, json=data, timeout=8)
        name = entity_id.split(".")[-1].replace("_", " ").capitalize()
        verb = {"on": "encendido", "off": "apagado", "toggle": "cambiado"}.get(action, action)
        return f"{name} {verb}."
    except Exception as e:
        return f"Error HA: {e}"


# ─── eWeLink ──────────────────────────────────────────────────────────────────

_EWELINK_TOKEN: str = ""

_EWELINK_REGIONS = {"eu": "eu-apia.coolkit.cc", "us": "us-apia.coolkit.cc", "cn": "cn-apia.coolkit.cc"}


async def _ewelink_login(client: httpx.AsyncClient) -> str:
    global _EWELINK_TOKEN
    region = os.environ.get("EWELINK_REGION", "eu")
    host   = _EWELINK_REGIONS.get(region, _EWELINK_REGIONS["eu"])
    try:
        r = await client.post(f"https://{host}/v2/user/login", json={
            "email": os.environ.get("EWELINK_EMAIL", ""),
            "password": os.environ.get("EWELINK_PASSWORD", ""),
            "countryCode": "+54",
        }, headers={"Content-Type": "application/json",
                    "X-CK-Appid": "YzfeftUVcZ6twZw1OoVKPRFYTrGEg01Q"}, timeout=10)
        data = r.json()
        if data.get("error") == 0:
            _EWELINK_TOKEN = data["data"]["at"]
    except Exception as e:
        logger.warning(f"eWeLink login: {e}")
    return _EWELINK_TOKEN


async def _ewelink_get_devices(client: httpx.AsyncClient) -> list[Device]:
    email  = os.environ.get("EWELINK_EMAIL", "")
    passwd = os.environ.get("EWELINK_PASSWORD", "")
    if not email or not passwd:
        return []
    global _EWELINK_TOKEN
    if not _EWELINK_TOKEN:
        await _ewelink_login(client)
    if not _EWELINK_TOKEN:
        return []
    region = os.environ.get("EWELINK_REGION", "eu")
    host   = _EWELINK_REGIONS.get(region, _EWELINK_REGIONS["eu"])
    try:
        r = await client.get(f"https://{host}/v2/device/thing",
                             headers={"Authorization": f"Bearer {_EWELINK_TOKEN}",
                                      "Content-Type": "application/json"}, timeout=10)
        devices = []
        for item in r.json().get("data", {}).get("thingList", []):
            d = item.get("itemData", {})
            is_on = d.get("params", {}).get("switch", "off") == "on"
            devices.append(Device(id=d.get("deviceid", ""), name=d.get("name", "Dispositivo eWeLink"),
                                  type="switch", state={"state": "on" if is_on else "off", "on": is_on},
                                  platform="ewelink"))
        return devices
    except Exception as e:
        logger.warning(f"eWeLink get_devices: {e}")
        return []


async def _ewelink_control(client: httpx.AsyncClient, device_id: str, action: str) -> str:
    global _EWELINK_TOKEN
    if not _EWELINK_TOKEN:
        await _ewelink_login(client)
    if not _EWELINK_TOKEN:
        return "No pude conectar a eWeLink."
    region = os.environ.get("EWELINK_REGION", "eu")
    host   = _EWELINK_REGIONS.get(region, _EWELINK_REGIONS["eu"])
    val    = "on" if action == "on" else "off"
    try:
        r = await client.post(f"https://{host}/v2/device/thing/status",
                              headers={"Authorization": f"Bearer {_EWELINK_TOKEN}",
                                       "Content-Type": "application/json"},
                              json={"type": 1, "id": device_id, "params": {"switch": val}}, timeout=10)
        if r.json().get("error") == 0:
            return f"Dispositivo {val}."
        return f"Error eWeLink: {r.json().get('msg', 'desconocido')}"
    except Exception as e:
        return f"Error eWeLink: {e}"


# ─── Tuya ─────────────────────────────────────────────────────────────────────

_TUYA_TOKEN = ""
_TUYA_TOKEN_EXPIRY = 0

_TUYA_REGIONS = {"eu": "openapi.tuyaeu.com", "us": "openapi.tuyaus.com", "cn": "openapi.tuyacn.com"}


def _tuya_sign(access_id: str, secret: str, t: str, token: str = "") -> str:
    s = f"{access_id}{token}{t}"
    return hmac.new(secret.encode(), s.encode(), hashlib.sha256).hexdigest().upper()


async def _tuya_get_token(client: httpx.AsyncClient) -> str:
    global _TUYA_TOKEN, _TUYA_TOKEN_EXPIRY
    access_id = os.environ.get("TUYA_ACCESS_ID", "")
    secret    = os.environ.get("TUYA_ACCESS_SECRET", "")
    region    = os.environ.get("TUYA_REGION", "eu")
    host      = _TUYA_REGIONS.get(region, _TUYA_REGIONS["eu"])
    t = str(int(time.time() * 1000))
    try:
        r = await client.get(f"https://{host}/v1.0/token?grant_type=1",
                             headers={"client_id": access_id, "sign": _tuya_sign(access_id, secret, t),
                                      "t": t, "sign_method": "HMAC-SHA256"}, timeout=10)
        data = r.json()
        if data.get("success"):
            _TUYA_TOKEN = data["result"]["access_token"]
            _TUYA_TOKEN_EXPIRY = int(time.time()) + data["result"].get("expire_time", 7200)
    except Exception as e:
        logger.warning(f"Tuya token: {e}")
    return _TUYA_TOKEN


def _tuya_headers(access_id: str, secret: str) -> dict:
    global _TUYA_TOKEN, _TUYA_TOKEN_EXPIRY
    t = str(int(time.time() * 1000))
    return {"client_id": access_id, "access_token": _TUYA_TOKEN,
            "sign": _tuya_sign(access_id, secret, t, _TUYA_TOKEN),
            "t": t, "sign_method": "HMAC-SHA256"}


async def _tuya_get_devices(client: httpx.AsyncClient) -> list[Device]:
    access_id = os.environ.get("TUYA_ACCESS_ID", "")
    secret    = os.environ.get("TUYA_ACCESS_SECRET", "")
    region    = os.environ.get("TUYA_REGION", "eu")
    if not access_id or not secret:
        return []
    global _TUYA_TOKEN, _TUYA_TOKEN_EXPIRY
    if not _TUYA_TOKEN or time.time() >= _TUYA_TOKEN_EXPIRY:
        await _tuya_get_token(client)
    host = _TUYA_REGIONS.get(region, _TUYA_REGIONS["eu"])
    try:
        r = await client.get(f"https://{host}/v1.0/iot-01/associated-users/devices",
                             headers=_tuya_headers(access_id, secret), timeout=10)
        devices = []
        for d in r.json().get("result", {}).get("devices", []):
            is_on = d.get("online", False)
            devices.append(Device(id=d.get("id", ""), name=d.get("name", "Dispositivo Tuya"),
                                  type="switch", state={"state": "on" if is_on else "off", "on": is_on},
                                  platform="tuya"))
        return devices
    except Exception as e:
        logger.warning(f"Tuya get_devices: {e}")
        return []


async def _tuya_control(client: httpx.AsyncClient, device_id: str, action: str, params: dict = None) -> str:
    access_id = os.environ.get("TUYA_ACCESS_ID", "")
    secret    = os.environ.get("TUYA_ACCESS_SECRET", "")
    region    = os.environ.get("TUYA_REGION", "eu")
    if not access_id or not secret:
        return "Tuya no configurado."
    global _TUYA_TOKEN, _TUYA_TOKEN_EXPIRY
    if not _TUYA_TOKEN or time.time() >= _TUYA_TOKEN_EXPIRY:
        await _tuya_get_token(client)
    host = _TUYA_REGIONS.get(region, _TUYA_REGIONS["eu"])
    commands = params.get("commands") if params else None
    if not commands:
        commands = [{"code": "switch_1", "value": action == "on"}]
    try:
        r = await client.post(f"https://{host}/v1.0/iot-03/devices/{device_id}/commands",
                              headers=_tuya_headers(access_id, secret),
                              json={"commands": commands}, timeout=10)
        if r.json().get("success"):
            return f"Dispositivo {'encendido' if action == 'on' else 'apagado'}."
        return f"Error Tuya: {r.json().get('msg', 'desconocido')}"
    except Exception as e:
        return f"Error Tuya: {e}"


# ─── Servicio unificado ───────────────────────────────────────────────────────

async def get_all_devices() -> list[Device]:
    async with httpx.AsyncClient(verify=False) as client:
        results = await asyncio.gather(
            _ha_get_devices(client),
            _ewelink_get_devices(client),
            _tuya_get_devices(client),
        )
    return [d for group in results for d in group]


def _find_device(devices: list[Device], query: str) -> Device | None:
    q = query.lower()
    for d in devices:
        if q in d.name.lower() or q in d.id.lower():
            return d
    return None


async def control_device(name: str, action: str, params: dict = None) -> str:
    devices = await get_all_devices()
    dev = _find_device(devices, name)
    if not dev:
        return f"No encontré ningún dispositivo llamado '{name}'."
    async with httpx.AsyncClient(verify=False) as client:
        if dev.platform == "ha":
            return await _ha_control(client, dev.id, action, params)
        if dev.platform == "ewelink":
            return await _ewelink_control(client, dev.id, action)
        if dev.platform == "tuya":
            return await _tuya_control(client, dev.id, action, params)
    return "Plataforma no soportada."


async def list_devices() -> list[dict]:
    devices = await get_all_devices()
    return [d.to_dict() for d in devices]


async def get_sensors() -> list[dict]:
    devices = await get_all_devices()
    return [d.to_dict() for d in devices if d.type == "sensor"]
