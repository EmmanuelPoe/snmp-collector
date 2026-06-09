from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from auth import get_current_user, require_role
from database import get_db
from models import CollectionConfig, User
from schemas import CollectionConfigCreate, CollectionConfigResponse, CollectionConfigUpdate
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["configuration"])

SUPPORTED_MODULES = ["if_mib", "host_resources", "ucd_snmp", "cisco_memory", "cisco_cpu"]


@router.get("/modules")
def list_modules(_: User = Depends(get_current_user)):
    return SUPPORTED_MODULES


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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Config for OID {config.oid} already exists")
    db_config = CollectionConfig(**config.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


@router.put("/configs/{config_id}", response_model=CollectionConfigResponse)
def update_config(
    config_id: int,
    updates: CollectionConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    db_config = db.query(CollectionConfig).filter(CollectionConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    changes = updates.model_dump(exclude_unset=True)
    if db_config.required and changes.get("enabled") is False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"OID {db_config.oid_name} is required by the metrics pipeline and cannot be disabled")
    for field, value in changes.items():
        setattr(db_config, field, value)
    db.commit()
    db.refresh(db_config)
    return db_config


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_config(
    config_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    db_config = db.query(CollectionConfig).filter(CollectionConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    if db_config.required:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"OID {db_config.oid_name} is required by the metrics pipeline and cannot be deleted")
    db.delete(db_config)
    db.commit()
