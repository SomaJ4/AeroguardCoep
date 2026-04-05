import asyncio
import uuid
import httpx
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from db.supabase import supabase
from models.schemas import AnalyzeResult, BatchResult, BatchResultItem
from services import vision_client
from services.risk import classify_risk
from services.dispatch import dispatch_drone

router = APIRouter(prefix="/upload", tags=["upload"])

BUCKET = "Videos"


@router.post("/video")
async def upload_video(file: UploadFile = File(...)):
    """
    Upload a video file to Supabase Storage.
    Returns the public URL for the vision service to analyze.
    """
    if not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")

    ext = file.filename.split(".")[-1] if "." in file.filename else "mp4"
    filename = f"{uuid.uuid4()}.{ext}"

    contents = await file.read()

    try:
        supabase.storage.from_(BUCKET).upload(
            path=filename,
            file=contents,
            file_options={"content-type": file.content_type},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    public_url = supabase.storage.from_(BUCKET).get_public_url(filename)

    return {
        "filename": filename,
        "url": public_url,
        "message": "Send this URL to the vision service for analysis"
    }


@router.post("/videos")
async def upload_videos(
    files: list[UploadFile] = File(...),
    camera_ids: list[str] = Form(...),
):
    """
    Upload N video files and fan out concurrent POST /analyze calls to the Vision Service.
    Returns a BatchResult with per-video success/failure outcomes.
    """
    # Validation
    if not files:
        raise HTTPException(status_code=400, detail="At least one video file is required")
    if len(files) != len(camera_ids):
        raise HTTPException(
            status_code=400,
            detail=f"files and camera_ids counts must match ({len(files)} files, {len(camera_ids)} camera_ids)",
        )
    for i, cid in enumerate(camera_ids):
        if not cid or not cid.strip():
            raise HTTPException(
                status_code=400,
                detail=f"camera_id at index {i} is missing or empty",
            )

    # Read all file bytes upfront before any other processing
    file_data: list[tuple[bytes, str, str]] = []  # (contents, filename, content_type)
    for i, f in enumerate(files):
        contents = await f.read()
        if not contents:
            raise HTTPException(status_code=400, detail=f"File at index {i} is empty")
        ct = f.content_type or "video/mp4"
        if ct == "application/octet-stream":
            ct = "video/mp4"
        ext = f.filename.split(".")[-1] if f.filename and "." in f.filename else "mp4"
        file_data.append((contents, ext, ct))

    # Upload files to Supabase Storage sequentially via thread executor
    async def upload_one(contents: bytes, ext: str, ct: str) -> str:
        filename = f"{uuid.uuid4()}.{ext}"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: supabase.storage.from_(BUCKET).upload(
                path=filename,
                file=contents,
                file_options={"content-type": ct},
            )
        )
        public_url = supabase.storage.from_(BUCKET).get_public_url(filename)

        # Poll until CDN serves the file with actual content (up to 15s)
        async with httpx.AsyncClient(timeout=10.0) as client:
            for _ in range(15):
                try:
                    r = await client.head(public_url)
                    content_length = int(r.headers.get("content-length", "0"))
                    if r.status_code == 200 and content_length > 0:
                        break
                except Exception:
                    pass
                await asyncio.sleep(1.0)

        return public_url

    try:
        public_urls = []
        for contents, ext, ct in file_data:
            url = await upload_one(contents, ext, ct)
            public_urls.append(url)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    # Fetch camera coordinates for each camera_id
    unique_camera_ids = list(set(camera_ids))
    try:
        cam_resp = supabase.table("cameras").select("id,lat,lng").in_("id", unique_camera_ids).execute()
        camera_coords = {cam["id"]: (cam["lat"], cam["lng"]) for cam in (cam_resp.data or [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch camera coordinates: {str(e)}")

    missing = [cid for cid in camera_ids if cid not in camera_coords]
    if missing:
        raise HTTPException(status_code=400, detail=f"Camera(s) not found: {missing}")

    # Fan out concurrent POST /analyze calls
    session_ids = [str(uuid.uuid4()) for _ in files]
    coros = [
        vision_client.analyze(
            stream_url=url,
            camera_id=camera_ids[i],
            session_id=session_ids[i],
            lat=camera_coords[camera_ids[i]][0],
            lng=camera_coords[camera_ids[i]][1],
        )
        for i, url in enumerate(public_urls)
    ]
    outcomes = await asyncio.gather(*coros, return_exceptions=True)

    # Aggregate results
    items = []
    for i, outcome in enumerate(outcomes):
        if isinstance(outcome, Exception):
            items.append(BatchResultItem(
                camera_id=camera_ids[i],
                url=public_urls[i],
                status="failed",
                error=str(outcome),
            ))
        else:
            # Save incident to Supabase and trigger dispatch if needed
            try:
                risk_level = classify_risk(float(outcome.risk_score))

                # Map Om's incident types to DB-valid values
                TYPE_MAP = {
                    "vehicle_collision": "accident",
                    "unknown_anomaly":   "intrusion",
                    "normal":            "patrol",
                    "crowd_gathering":   "crowd_gathering",
                }
                db_incident_type = TYPE_MAP.get(outcome.incident_type, outcome.incident_type)

                incident_data = {
                    "id": outcome.id,
                    "camera_id": outcome.camera_id,
                    "incident_type": db_incident_type,
                    "risk_score": outcome.risk_score,
                    "confidence": outcome.confidence,
                    "risk_level": risk_level,
                    "lat": outcome.lat,
                    "lng": outcome.lng,
                    "snapshot_url": outcome.snapshot_url,
                    "status": "open",
                    "human_crowd": outcome.human_crowd or 0,
                    "crowd_score": outcome.crowd_score or 0.0,
                }
                supabase.table("incidents").upsert(incident_data).execute()

                # Compute and store severity
                from services.severity import update_incident_severity
                fresh = supabase.table("incidents").select("*").eq("id", outcome.id).single().execute()
                if fresh.data:
                    update_incident_severity(outcome.id, fresh.data)

                if risk_level == "high":
                    async def _dispatch_and_log(incident_id: str):
                        import logging as _log
                        try:
                            result = await dispatch_drone(incident_id)
                            _log.getLogger(__name__).info("Dispatch success: %s", result)
                            # Check rerouting after new dispatch
                            from services.rerouting import check_rerouting
                            await check_rerouting(trigger_incident_id=incident_id)
                        except Exception as _e:
                            _log.getLogger(__name__).error("Dispatch failed for %s: %s", incident_id, _e)
                    asyncio.create_task(_dispatch_and_log(outcome.id))
                elif risk_level == "medium":
                    supabase.table("alerts").insert({
                        "incident_id": outcome.id,
                        "risk_level": "medium",
                        "message": "Medium-risk incident detected. Manual drone dispatch required.",
                    }).execute()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error("Post-analyze processing failed: %s", e)

            items.append(BatchResultItem(
                camera_id=camera_ids[i],
                url=public_urls[i],
                status="success",
                result=outcome,
            ))

    batch = BatchResult(items=items)
    successes = sum(1 for item in items if item.status == "success")

    if successes == len(items):
        status_code = 200
    elif successes == 0:
        status_code = 502
    else:
        status_code = 207

    return JSONResponse(
        status_code=status_code,
        content=batch.model_dump(),
    )
