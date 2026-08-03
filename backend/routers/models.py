from fastapi import APIRouter
from ..services import ollama as ol

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def get_models():
    models = await ol.list_models()
    return {"models": models}


@router.get("/status")
async def get_status():
    online = await ol.is_online()
    return {"online": online}
