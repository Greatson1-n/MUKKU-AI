from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.models import User, AppSetting
from app.schemas.schemas import SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["Settings"])

@router.get("")
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_settings = db.query(AppSetting).filter(AppSetting.user_id == current_user.id).all()
    user_map = {s.key: s.value for s in user_settings}

    return {
        "ollama_host": settings.OLLAMA_HOST,
        "ollama_model": user_map.get("ollama_model", settings.OLLAMA_MODEL),
        "embedding_model": settings.EMBEDDING_MODEL,
        "vision_model": settings.VISION_MODEL,
        "temperature": float(user_map.get("temperature", 0.7)),
        "system_prompt": user_map.get("system_prompt", settings.DEFAULT_SYSTEM_PROMPT),
        "language": user_map.get("language", "en"),
        "response_style": user_map.get("response_style", "balanced"),
        "web_search_enabled": user_map.get("web_search_enabled", "false").lower() == "true",
        "memory_enabled": user_map.get("memory_enabled", "true").lower() == "true",
        "theme": user_map.get("theme", "dark"),
    }

@router.patch("")
def update_settings(
    req: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    updates = req.model_dump(exclude_unset=True)
    for k, v in updates.items():
        if v is None:
            continue
        val_str = str(v).lower() if isinstance(v, bool) else str(v)
        setting = db.query(AppSetting).filter(
            AppSetting.user_id == current_user.id,
            AppSetting.key == k
        ).first()
        if setting:
            setting.value = val_str
        else:
            setting = AppSetting(user_id=current_user.id, key=k, value=val_str)
            db.add(setting)

    db.commit()
    return get_settings(db, current_user)
