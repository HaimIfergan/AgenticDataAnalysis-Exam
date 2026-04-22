import pytest
import pandas as pd
from backend.agents.agent_manager import AgentManager

@pytest.mark.asyncio
@pytest.mark.integration
async def test_calculate_mean(sample_dataframe):
    """Vérifie que l'agent calcule la moyenne d'âge."""
    agent = AgentManager()
    # On simule une question sur le dataframe fourni en fixture
    query = "Quelle est la moyenne d'âge dans ce dataset ?"
    response = await agent.ask(query, df=sample_dataframe)
    
    # La moyenne de [25, 30, 35, 40, 45, 50, 55, 60] est 42.5
    assert "42.5" in str(response["output"])

@pytest.mark.asyncio
@pytest.mark.integration
async def test_scatter_plot(sample_dataframe):
    """Vérifie que l'agent génère bien un objet graphique."""
    agent = AgentManager()
    query = "Fais un scatter plot income vs age"
    response = await agent.ask(query, df=sample_dataframe)
    
    assert "figure" in response or "plotly" in str(response).lower()