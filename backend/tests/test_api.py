import pytest
import httpx
from fastapi.testclient import TestClient
from backend.api.main import app # Vérifie le chemin

@pytest.fixture
async def client():
    """Crée un client async pour les tests API."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_health_check(client):
    """Vérifie que l'API est en ligne."""
    response = await client.get("/health") # Adapte si ta route est /api/health
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_auth_register(client):
    """Test: Inscription d'un utilisateur."""
    response = await client.post("/api/auth/register", json={
        "username": "test_user_pytest",
        "email": "pytest@example.com",
        "password": "securepassword123"
    })
    # 200 si nouveau, 400 si le test a déjà été lancé
    assert response.status_code in [200, 400]

@pytest.mark.asyncio
async def test_auth_login(client):
    """Test: Récupération du token JWT."""
    # On s'assure que l'utilisateur existe d'abord
    await client.post("/api/auth/register", json={
        "username": "test_login", "email": "l@ex.com", "password": "password"
    })
    
    response = await client.post("/api/auth/login", data={
        "username": "test_login",
        "password": "password"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

@pytest.mark.security
async def test_unauthorized_access(client):
    """Vérifie que les routes protégées bloquent sans token."""
    response = await client.get("/api/history")
    assert response.status_code == 401