from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from auth import get_current_user, require_role
from database import get_db
from models import CollectionConfig, User
from schemas import CollectionConfigCreate, CollectionConfigResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["configuration"])


@router.get("/configs", response_model=List[CollectionConfigResponse])
def list_configs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(CollectionConfig).all()


@router.post("/configs", response_model=CollectionConfigResponse, status_code=status.HTTP_201_CREATED)
def create_config(
    config: CollectionConfigCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    existing = db.query(CollectionConfig).filter(CollectionConfig.oid == config.oid).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Config for OID {config.oid} already exists"
        )
    db_config = CollectionConfig(**config.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config
