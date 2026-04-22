import pytest
import asyncio
from backend.security.sandbox import execute_sandboxed_code # Ton module sandbox

@pytest.mark.asyncio
@pytest.mark.security
async def test_code_execution_sandbox():
    """Vérifie que les tentatives d'évasion sont bloquées."""
    malicious_code_attempts = [
        "__import__('os').system('rm -rf /')",
        "open('/etc/passwd', 'r').read()",
        "__import__('subprocess').call(['ls'])"
    ]
    
    for attempt in malicious_code_attempts:
        result = await execute_sandboxed_code(attempt)
        # On attend un message d'erreur ou un refus, pas une exécution réussie
        assert "Forbidden" in result or "Error" in result or "blocked" in result.lower()

@pytest.mark.asyncio
@pytest.mark.security
async def test_resource_limits():
    """Vérifie que les boucles infinies sont stoppées par timeout."""
    infinite_loop = "while True: pass"
    
    # La fonction doit rendre la main rapidement malgré la boucle
    result = await execute_sandboxed_code(infinite_loop)
    assert "Timeout" in result or "limit" in result.lower()