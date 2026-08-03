"""
Image Library router — GET/DELETE for the user's saved generated images.

GET    /api/library          → paginated list with metadata
GET    /api/library/stats    → total count + disk usage
DELETE /api/library/{id}     → delete image + metadata
"""
from fastapi import APIRouter, HTTPException
from ..services import image_library as lib

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("")
async def list_library(limit: int = 200, offset: int = 0):
    images = await lib.list_images(limit=limit, offset=offset)
    # Attach URL for each image
    for img in images:
        img["url"] = f"/api/images/file/{img['filename']}"
    return images


@router.get("/stats")
async def library_stats():
    return await lib.get_stats()


@router.delete("/{img_id}", status_code=204)
async def delete_image(img_id: str):
    deleted = await lib.delete_image(img_id)
    if not deleted:
        raise HTTPException(404, "Image not found")
