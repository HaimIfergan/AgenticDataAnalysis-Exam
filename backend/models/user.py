# backend/models/user.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from backend.models.database import Base

class User(Base):
    __tablename__ = "users"

    # Index ajoutés pour la performance des requêtes (Prérequis 2.3)
    id = Column(Integer, primary_key=True, index=True)
    
    # Contraintes d'unicité et indexation
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    # Timestamps automatiques (Schéma image_2b1246.png)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())