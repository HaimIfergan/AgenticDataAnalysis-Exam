import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Chargement des variables d'environnement (.env)
load_dotenv()

# Récupération de l'URL de la base de données
# Par défaut, utilise SQLite pour le développement local si DATABASE_URL n'est pas définie
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")

# Création de l'moteur SQLAlchemy
# L'argument connect_args={"check_same_thread": False} est indispensable uniquement pour SQLite
# Déterminez les connect_args dynamiquement
connect_args = {}
if "sqlite" in SQLALCHEMY_DATABASE_URL:
    connect_args["check_same_thread"] = False

    SQLALCHEMY_DATABASE_URL, connect_args=connect_args
)

# Configuration de la fabrique de sessions (Prérequis 2.3 : Gestion de session)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Classe de base pour la création des modèles ORM
Base = declarative_base()

# Dépendance pour injecter la session de base de données dans les endpoints FastAPI
# Assure que chaque requête a sa propre session et qu'elle est fermée après usage
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()