import pytest
from backend.models.database import SessionLocal
from backend.models.models import AnalysisSession

@pytest.mark.asyncio
@pytest.mark.persistence
async def test_analysis_history():
    """Vérifie que les sessions sont enregistrées en DB."""
    db = SessionLocal()
    try:
        # 1. Création manuelle d'une session
        session = AnalysisSession(user_id=1, query="Test persistence", response="Ok")
        db.add(session)
        db.commit()
        
        # 2. Vérification
        saved = db.query(AnalysisSession).filter_by(query="Test persistence").first()
        assert saved is not None
        assert saved.response == "Ok"
    finally:
        db.close()