import io
import logging

from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
import structlog
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import pandas as pd

from backend.models.database import engine, Base, get_db
from backend.models.user import User
from backend.api.auth import hash_password, verify_password, create_access_token
from backend.agents.agent_manager import AgentManager
from backend.agents import dataset_store

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
    version="1.0.0",
)


@app.on_event("startup")
def startup_event():
    logger.info("Initialisation de la base de données : création des tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables créées avec succès !")


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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/auth/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.email)
    ).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    new_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
    )
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


def _persist_dataset_bytes(user_id: int, filename: str, content: bytes):
    """Save CSV/Excel bytes to disk and register them for the analysis agent."""
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    filename = filename or "dataset.csv"
    lower = filename.lower()
    try:
        if lower.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
            csv_name = filename.rsplit(".", 1)[0] + ".csv"
            csv_buf = io.StringIO()
            df.to_csv(csv_buf, index=False)
            item = dataset_store.save_upload(
                user_id,
                csv_name,
                csv_buf.getvalue().encode("utf-8"),
                description=f"Uploaded Excel {filename}",
            )
        else:
            item = dataset_store.save_upload(
                user_id,
                filename,
                content,
                description=f"Uploaded dataset {filename}",
            )
            pd.read_csv(item.data_path, nrows=5)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Impossible de lire le fichier : {e}")

    preview = pd.read_csv(item.data_path, nrows=5)
    item.data_description = (
        f"{item.data_description}. Columns: {list(preview.columns)}. "
        f"Shape preview rows={len(preview)}."
    )
    return item, preview


@app.post("/api/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    user_id: int = Form(1),
    db: Session = Depends(get_db),
):
    """Enregistre un CSV/Excel et l'associe à l'utilisateur pour l'agent."""
    content = await file.read()
    item, preview = _persist_dataset_bytes(user_id, file.filename or "dataset.csv", content)
    return {
        "status": "ok",
        "variable_name": item.variable_name,
        "path": item.data_path,
        "columns": list(preview.columns),
        "rows_preview": len(preview),
    }


@app.get("/api/chat/history/{user_id}")
async def get_chat_history(user_id: int, db: Session = Depends(get_db)):
    """Récupère l'historique complet depuis la base de données."""
    agent = AgentManager(db=db, user_id=user_id)
    return agent.load_history()


@app.post("/api/chat/ask")
async def ask_agent(
    user_id: int = 1,
    query: str = "",
    file: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
):
    """
    Transmet la query au vrai agent LangGraph (ReAct) sur le dataset chargé.
    Accepte un CSV/Excel optionnel (multipart) pour (re)charger le dataset
    dans le même appel. Retourne stdout d'exécution et JSON Plotly ({output, fig}).
    """
    query = (query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="La requête ne peut pas être vide")

    if file is not None and file.filename:
        content = await file.read()
        if content:
            _persist_dataset_bytes(user_id, file.filename, content)

    agent = AgentManager(db=db, user_id=user_id)
    result = await agent.ask(query)

    output = result.get("output") or result.get("message") or ""
    fig = result.get("fig") or result.get("figure")

    return {
        "status": result.get("status", "success"),
        "output": output,
        "fig": fig,
        "figure": fig,
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
