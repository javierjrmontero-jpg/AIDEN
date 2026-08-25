import os
import time

import psutil
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter()

# Estado previo de los contadores de red para calcular tasa entre llamadas.
_last_net = {"t": 0.0, "rx": 0, "tx": 0}


def _temperature() -> float | None:
    """Temperatura del paquete de CPU, si el kernel la expone."""
    try:
        sensors = psutil.sensors_temperatures()
    except Exception:
        return None
    for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
        if sensors.get(key):
            return round(sensors[key][0].current, 1)
    return None


# El compose monta la raíz del host en /hostfs (solo lectura). Sin ese montaje
# psutil mediría el sistema de archivos del contenedor, no el del servidor.
_DISK_PATH = "/hostfs" if os.path.ismount("/hostfs") else "/"


@router.get("/system/vitals")
async def system_vitals(current_user: User = Depends(get_current_user)):
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(_DISK_PATH)
    net = psutil.net_io_counters()
    now = time.monotonic()

    # Primera llamada: sin ventana previa no hay tasa que calcular.
    elapsed = now - _last_net["t"]
    if _last_net["t"] and elapsed > 0:
        rx = (net.bytes_recv - _last_net["rx"]) / elapsed
        tx = (net.bytes_sent - _last_net["tx"]) / elapsed
    else:
        rx = tx = 0.0
    _last_net.update(t=now, rx=net.bytes_recv, tx=net.bytes_sent)

    return {
        "cpu": psutil.cpu_percent(interval=None),
        "cpu_cores": psutil.cpu_count(),
        "memory": mem.percent,
        "memory_used_gb": round(mem.used / 1024**3, 1),
        "memory_total_gb": round(mem.total / 1024**3, 1),
        "disk": disk.percent,
        "disk_free_gb": round(disk.free / 1024**3, 1),
        "disk_scope": "host" if _DISK_PATH == "/hostfs" else "contenedor",
        "temperature": _temperature(),
        "uptime_seconds": int(time.time() - psutil.boot_time()),
        "processes": len(psutil.pids()),
        "net_rx_mbps": round(rx / 1024**2, 2),
        "net_tx_mbps": round(tx / 1024**2, 2),
    }
