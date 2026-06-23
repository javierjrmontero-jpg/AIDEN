from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import get_current_user
from app.models.user import User
from app.services.domotica.service import (
    get_all_devices, control_device, list_devices, get_sensors
)

router = APIRouter(prefix="/domotica", tags=["domotica"])


class ControlRequest(BaseModel):
    device:  str
    action:  str          # on | off | toggle | scene
    params:  dict = {}


@router.get("/devices")
async def devices(current_user: User = Depends(get_current_user)):
    return await list_devices()


@router.get("/sensors")
async def sensors(current_user: User = Depends(get_current_user)):
    return await get_sensors()


@router.post("/control")
async def control(body: ControlRequest, current_user: User = Depends(get_current_user)):
    if body.action not in ("on", "off", "toggle", "scene"):
        raise HTTPException(400, "action must be one of: on, off, toggle, scene")
    result = await control_device(body.device, body.action, body.params or None)
    return {"result": result}
