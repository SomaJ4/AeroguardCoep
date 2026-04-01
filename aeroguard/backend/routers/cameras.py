from fastapi import APIRouter, HTTPException
from db.supabase import supabase
from models.schemas import CameraCreate, CameraUpdate, CameraOut

router = APIRouter(prefix="/cameras", tags=["cameras"])

@router.get("", response_model=list[CameraOut])
def get_cameras():
    resp = supabase.table("cameras").select("*").execute()
    return resp.data

@router.post("", response_model=CameraOut, status_code=201)
def create_camera(body: CameraCreate):
    resp = supabase.table("cameras").insert(body.model_dump()).execute()
    return resp.data[0]

@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: str, body: CameraUpdate):
    existing = supabase.table("cameras").select("id").eq("id", camera_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Camera not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    resp = supabase.table("cameras").update(updates).eq("id", camera_id).execute()
    return resp.data[0]
