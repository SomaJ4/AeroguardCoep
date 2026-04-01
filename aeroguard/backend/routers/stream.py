import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from db.supabase import supabase

router = APIRouter(prefix="/stream", tags=["stream"])


async def _proxy_stream(stream_url: str):
    async def generator():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", stream_url) as r:
                async for chunk in r.aiter_bytes(chunk_size=8192):
                    yield chunk
    return StreamingResponse(generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/camera/{camera_id}")
async def camera_feed(camera_id: str):
    resp = supabase.table("cameras").select("stream_url").eq("id", camera_id).single().execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Camera not found")
    stream_url = resp.data.get("stream_url")
    if not stream_url:
        raise HTTPException(status_code=503, detail="Stream unavailable")
    return await _proxy_stream(stream_url)


@router.get("/{drone_id}")
async def drone_feed(drone_id: str):
    resp = supabase.table("drones").select("stream_url").eq("id", drone_id).single().execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Drone not found")
    stream_url = resp.data.get("stream_url")
    if not stream_url:
        raise HTTPException(status_code=503, detail="Stream unavailable")
    return await _proxy_stream(stream_url)
