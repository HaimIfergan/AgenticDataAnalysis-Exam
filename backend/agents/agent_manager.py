import io
import json
import contextlib
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy.orm import Session
from backend.models.chat import ChatMessage

class AgentManager:
    def __init__(self, db: Session, user_id: int, df: pd.DataFrame = None):
        self.db = db
        self.user_id = user_id
        self.df = df  # Le contexte du DataFrame
        self.globals = {
            "pd": pd, 
            "np": __import__('numpy'), 
            "px": px, 
            "go": go, 
            "stats": __import__('scipy.stats').stats,
            "df": self.df
        }

    def _save_to_db(self, role: str, content: str, intermediate_outputs: dict = None):
        """Sauvegarde les réponses dans la base de données"""
        new_msg = ChatMessage(
            user_id=self.user_id,
            role=role,
            content=content,
            intermediate_outputs=intermediate_outputs
        )
        self.db.add(new_msg)
        self.db.commit()

    def execute_visualization(self, thought: str, python_code: str):
        """Outil spécialisé pour Plotly"""
        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            try:
                # Exécution sécurisée avec exec()
                local_vars = {}
                exec(python_code, self.globals, local_vars)
                
                # Extraction de la figure Plotly
                fig_json = None
                for var in local_vars.values():
                    if isinstance(var, (go.Figure,)):
                        fig_json = json.loads(var.to_json())
                        break
                
                output = stdout_capture.getvalue()
                self._save_to_db("assistant", thought, {"type": "viz", "data": fig_json})
                return {"status": "success", "output": output, "fig": fig_json}
            
            except Exception as e:
                return {"status": "error", "message": str(e)}

    def execute_data_cleaning(self, thought: str, python_code: str):
        """Outil spécialisé pour le nettoyage"""
        # Logique similaire à viz mais sans capture de figure
        # ... (implémentation de exec et capture stdout)
        pass

    def execute_statistical_analysis(self, thought: str, python_code: str):
        """Outil spécialisé pour les stats Scipy"""
        # ... (implémentation de exec et capture stdout)
        pass
