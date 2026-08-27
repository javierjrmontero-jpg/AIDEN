"""
Despacho por proveedor de calendario.

La columna `provider` existía desde el principio en calendar_configs pero
nadie la leía: todo asumía Google. Este módulo es el único lugar que sabe
que hay más de un proveedor; el resto de MATE llama a estas funciones y
recibe siempre la misma forma de evento.
"""

from app.services.calendar import graph
from app.services.calendar import service as google


def _proveedor(config):
    return (getattr(config, "provider", None) or "google").lower()


async def list_upcoming_events(config, max_results: int = 10, days_ahead: int = 7):
    if _proveedor(config) == "microsoft":
        return await graph.list_upcoming_events(config, max_results, days_ahead)
    return await google.list_upcoming_events(config, max_results, days_ahead)


async def list_events_range(config, time_min: str, time_max: str, max_results: int = 50):
    if _proveedor(config) == "microsoft":
        return await graph.list_events_range(config, time_min, time_max, max_results)
    return await google.list_events_range(config, time_min, time_max, max_results)


async def create_event(config, **kwargs):
    if _proveedor(config) == "microsoft":
        return await graph.create_event(config, **kwargs)
    return await google.create_event(config, **kwargs)


def format_events_for_prompt(events: list) -> str:
    """Los eventos ya vienen normalizados, así que el formato es común."""
    return google.format_events_for_prompt(events)
