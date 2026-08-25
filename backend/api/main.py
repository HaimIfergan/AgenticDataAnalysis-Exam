import time
import uuid
import logging
import os
from typing import Callable, List

from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import structlog
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

# --- Imports de tes modules ---
from backend.models.database import engine, Base, get_db
from backend.models.user import User
from backend.models.chat import ChatMessage
from backend.api.auth import hash_password, verify_password, create_access_token
from backend.agents.agent_manager import AgentManager  # Import de l'Agent

# --- Configuration du Logging ---
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()

app = FastAPI(
    title="Agentic Data Analysis API",
    description="Backend avec Persistance de Session (Partie 2.5)",
    version="1.0.0"
)

# === AJOUT DE LA CRÉATION DES TABLES AU DÉMARRAGE ===
@app.on_event("startup")
def startup_event():
    logger.info("Initialisation de la base de données : création des tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables créées avec succès !")
# ====================================================

# --- Schémas Pydantic ---
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    is_active: bool
    class Config:
        from_attributes = True

# --- Middleware CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoints Authentification ---

@app.post("/api/auth/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter((User.username == user_in.username) | (User.email == user_in.email)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    new_user = User(username=user_in.username, email=user_in.email, hashed_password=hash_password(user_in.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect credentials")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# --- SECTION AGENT & PERSISTANCE (PARTIE 2.5) ---

@app.get("/api/chat/history/{user_id}")
async def get_chat_history(user_id: int, db: Session = Depends(get_db)):
    """
    ROUTE CRUCIALE POUR LE TEST CRITIQUE : 
    Récupère l'historique complet depuis la base de données.
    """
    agent = AgentManager(db=db, user_id=user_id)
    history = agent.load_history()
    return history

@app.post("/api/chat/ask")
async def ask_agent(user_id: int, query: str, db: Session = Depends(get_db)):
    """
    Implémente le Pattern ReAct avec persistance immédiate.
    """
    agent = AgentManager(db=db, user_id=user_id)
    
    # 1. Sauvegarde du message utilisateur en base
    agent._save_message(role="user", content=query)
    
    # 2. Simulation d'exécution d'outil (Exemple: Visualisation)
    # Dans la vraie logique, un LLM choisirait l'outil ici.
    result = agent.execute_visualization(
        thought=f"Analyse demandée : {query}",
        python_code="import plotly.express as px\nfig = px.bar(df, title='Analyse')" # df est passé par le contexte
    )
    
    return result

# --- Endpoints Standard ---
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)