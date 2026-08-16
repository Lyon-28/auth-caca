import uuid
import base64
import httpx
import os
from io import BytesIO
from PIL import Image
from app.config import settings

def optimize_image(raw: bytes, max_dimension: int = 512) -> bytes:
    img = Image.open(BytesIO(raw))
    img = img.convert("RGB")
    img.thumbnail((max_dimension, max_dimension))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()

async def _supabase_upload(filename: str, data: bytes) -> str:
    if not settings.supabase_url or not settings.supabase_service_key:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{settings.supabase_url}/storage/v1/object/{settings.supabase_storage_bucket}/{filename}",
            headers={"Authorization": f"Bearer {settings.supabase_service_key}", "Content-Type": "image/jpeg"},
            content=data,
        )
        r.raise_for_status()
        return f"{settings.supabase_url}/storage/v1/object/public/{settings.supabase_storage_bucket}/{filename}"

async def _imagekit_upload(filename: str, data: bytes) -> str:
    if not settings.imagekit_private_key:
        raise RuntimeError("skip")
    b64 = base64.b64encode(data).decode()
    async with httpx.AsyncClient(timeout=15, auth=(settings.imagekit_private_key, "")) as client:
        r = await client.post(
            "https://upload.imagekit.io/api/v1/files/upload",
            data={"file": f"data:image/jpeg;base64,{b64}", "fileName": filename, "useUniqueFileName": "false"},
        )
        r.raise_for_status()
        return r.json()["url"]

async def _imgbb_upload(filename: str, data: bytes) -> str:
    if not settings.imgbb_api_key:
        raise RuntimeError("skip")
    b64 = base64.b64encode(data).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post("https://api.imgbb.com/1/upload", data={"key": settings.imgbb_api_key, "image": b64, "name": filename})
        r.raise_for_status()
        return r.json()["data"]["url"]

async def _github_upload(filename: str, data: bytes) -> str:
    if not settings.github_storage_token or not settings.github_storage_repo:
        raise RuntimeError("skip")
    b64 = base64.b64encode(data).decode()
    async with httpx.AsyncClient(timeout=15, headers={"Authorization": f"token {settings.github_storage_token}"}) as client:
        path = f"avatars/{filename}"
        r = await client.put(
            f"https://api.github.com/repos/{settings.github_storage_repo}/contents/{path}",
            json={"message": f"upload {filename}", "content": b64, "branch": settings.github_storage_branch},
        )
        r.raise_for_status()
        return f"https://raw.githubusercontent.com/{settings.github_storage_repo}/{settings.github_storage_branch}/{path}"

async def _local_upload(filename: str, data: bytes) -> str:
    os.makedirs(settings.local_storage_path, exist_ok=True)
    path = os.path.join(settings.local_storage_path, filename)
    with open(path, "wb") as f:
        f.write(data)
    return f"{settings.local_storage_public_url}/{filename}"

PROVIDER_CHAIN = [_supabase_upload, _imagekit_upload, _imgbb_upload, _github_upload, _local_upload]

async def upload_avatar(raw_bytes: bytes) -> str:
    optimized = optimize_image(raw_bytes)
    filename = f"{uuid.uuid4().hex}.jpg"
    last_error = None
    for provider in PROVIDER_CHAIN:
        try:
            return await provider(filename, optimized)
        except Exception as e:
            last_error = e
            continue
    raise RuntimeError(f"all storage providers failed: {last_error}")