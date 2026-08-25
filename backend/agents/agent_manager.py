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

    def load_history(self, session_id: int = None):
        """Charge l'historique des messages depuis la base de données pour un utilisateur/session."""
        query = self.db.query(ChatMessage).filter(ChatMessage.user_id == self.user_id)
        if session_id:
            query = query.filter(ChatMessage.session_id == session_id)
        messages = query.order_by(ChatMessage.created_at.asc()).all()
        
        # Retourne les champs indispensables (id, created_at, role, content, etc.)
        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": str(msg.created_at) if msg.created_at else "",
                "intermediate_outputs": msg.intermediate_outputs
            }
            for msg in messages
        ]

    def _save_message(self, role: str, content: str, intermediate_outputs: dict = None):
        """Sauvegarde un message (utilisateur ou assistant) dans l'historique de la base de données."""
        new_msg = ChatMessage(
            user_id=self.user_id,
            role=role,
            content=content,
            intermediate_outputs=intermediate_outputs
        )
        self.db.add(new_msg)
        self.db.commit()
        self.db.refresh(new_msg)
        return new_msg

    def _save_to_db(self, role: str, content: str, intermediate_outputs: dict = None):
        """Alias interne pour la rétrocompatibilité"""
        return self._save_message(role, content, intermediate_outputs)

    def execute_visualization(self, thought: str, python_code: str):
        """Outil spécialisé pour Plotly"""
        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            try:
                local_vars = {}
                exec(python_code, self.globals, local_vars)
                
                fig_json = None
                for var in local_vars.values():
                    if isinstance(var, (go.Figure,)):
                        fig_json = json.loads(var.to_json())
                        break
                
                output = stdout_capture.getvalue()
                self._save_message("assistant", thought, {"type": "viz", "data": fig_json})
                return {"status": "success", "output": output, "fig": fig_json}
            
            except Exception as e:
                return {"status": "error", "message": str(e)}

    def execute_data_cleaning(self, thought: str, python_code: str):
        """Outil spécialisé pour le nettoyage"""
        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            try:
                local_vars = {}
                exec(python_code, self.globals, local_vars)
                
                if 'df' in local_vars and isinstance(local_vars['df'], pd.DataFrame):
                    self.df = local_vars['df']
                    self.globals['df'] = self.df

                output = stdout_capture.getvalue()
                self._save_message("assistant", thought, {"type": "cleaning", "output": output})
                return {"status": "success", "output": output}
            
            except Exception as e:
                return {"status": "error", "message": str(e)}

    def execute_statistical_analysis(self, thought: str, python_code: str):
        """Outil spécialisé pour les stats Scipy"""
        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            try:
                local_vars = {}
                exec(python_code, self.globals, local_vars)
                
                output = stdout_capture.getvalue()
                self._save_message("assistant", thought, {"type": "stats", "output": output})
                return {"status": "success", "output": output}
            
            except Exception as e:
                return {"status": "error", "message": str(e)}