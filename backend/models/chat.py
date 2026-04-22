from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, func
from backend.models.database import Base

class ChatMessage(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    # Clé étrangère pour lier le message à ton modèle User existant
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    role = Column(String, nullable=False)  # 'user' ou 'assistant'
    content = Column(String, nullable=False)
    
    # Crucial pour l'agent : stocke les graphiques Plotly et logs d'outils
    intermediate_outputs = Column(JSON, nullable=True) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())