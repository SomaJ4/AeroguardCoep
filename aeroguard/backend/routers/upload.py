import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from db.supabase import supabase

router = APIRouter(prefix="/upload", tags=["upload"])

BUCKET = "videos"


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
