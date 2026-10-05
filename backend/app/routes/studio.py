import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.meta_connection import MetaConnection, PROVIDER_INSTAGRAM, STATUS_ACTIVE
from app.services.instagram_service import publish_image_post, publish_video_post, TokenExpiredError
from app.services.meta_token_service import decrypt_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/studio", tags=["studio"])


class AnalyzeImageRequest(BaseModel):
    image_base64: str


class GenerateVideoRequest(BaseModel):
    image_base64: str
    prompt: str
    duration: str
    format: str
    style: str


class PublishStudioRequest(BaseModel):
    video_url: str
    media_type: str = "IMAGE"
    caption: str = ""
    hashtags: str = ""
    ig_user_id: Optional[str] = None


generation_jobs = {}


@router.post("/analyze-image")
async def analyze_image(request: AnalyzeImageRequest):
    try:
        suggested_prompts = [
            "Produto em destaque com movimento de câmera cinematográfico",
            "Zoom lento com transições suaves e cores vibrantes",
            "Estilo minimalista com fundo limpo e tipografia moderna",
            "Efeito dinâmico com múltiplas camadas e animações",
            "Apresentação profissional com narração sobre benefícios",
        ]

        return {
            "suggested_prompts": suggested_prompts,
            "image_analyzed": True,
        }
    except Exception as e:
        logger.error(f"Erro ao analisar imagem: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao analisar imagem")


@router.post("/generate-video")
async def generate_video(request: GenerateVideoRequest, db: AsyncSession = Depends(get_db)):
    try:
        job_id = str(uuid.uuid4())

        generation_jobs[job_id] = {
            "status": "processing",
            "progress": 0,
            "prompt": request.prompt,
            "duration": request.duration,
            "format": request.format,
            "style": request.style,
            "video_url": None,
        }

        return {
            "job_id": job_id,
            "status": "processing",
            "message": "Vídeo iniciado para geração",
        }
    except Exception as e:
        logger.error(f"Erro ao gerar vídeo: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao gerar vídeo")


@router.get("/generation-status/{job_id}")
async def get_generation_status(job_id: str):
    if job_id not in generation_jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    job = generation_jobs[job_id]
    if job["progress"] < 100:
        job["progress"] += 10
        if job["progress"] >= 100:
            job["progress"] = 100
            job["status"] = "completed"
            job["video_url"] = "https://example.com/video.mp4"

    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "video_url": job.get("video_url"),
    }


@router.post("/publish-video")
async def publish_video(
    request: PublishStudioRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == current_user.tenant_id,
            MetaConnection.provider == PROVIDER_INSTAGRAM,
            MetaConnection.status == STATUS_ACTIVE,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=400, detail="Instagram não conectado.")

    try:
        token = decrypt_token(conn.access_token_encrypted)
    except Exception:
        raise HTTPException(status_code=400, detail="Erro ao descriptografar token.")

    ig_id = request.ig_user_id or conn.ig_business_account_id or conn.meta_user_id
    if not ig_id:
        raise HTTPException(status_code=400, detail="Instagram Business ID não encontrado.")

    caption = request.caption or ""
    if request.hashtags:
        caption += f"\n\n{request.hashtags}"

    try:
        if request.media_type.upper() == "VIDEO":
            result = await publish_video_post(token, ig_id, request.video_url, caption)
        else:
            result = await publish_image_post(token, ig_id, request.video_url, caption)

        return {
            "success": True,
            "message": "Publicado com sucesso!",
            "media_id": result.get("id"),
        }
    except TokenExpiredError as e:
        raise HTTPException(status_code=401, detail=f"Token expirado: {e}")
    except Exception as e:
        logger.error(f"Erro ao publicar: {e}")
        raise HTTPException(status_code=500, detail="Erro ao publicar no Instagram.")
