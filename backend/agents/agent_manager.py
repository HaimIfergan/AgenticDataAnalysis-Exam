import asyncio
import io
import json
import os
import pickle
import tempfile
import contextlib
from typing import List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy.orm import Session

from backend.models.chat import ChatMessage
from backend.agents import dataset_store
from Pages.backend import PythonChatbot
from Pages.data_models import InputData

# Keep one chatbot instance per user for multi-turn memory in-process
_chatbots = {}


class AgentManager:
    def __init__(self, db: Session = None, user_id: int = None, df: pd.DataFrame = None):
        self.db = db
        self.user_id = user_id if user_id is not None else 0
        self.df = df  # Le contexte du DataFrame
        self.globals = {
            "pd": pd,
            "np": __import__("numpy"),
            "px": px,
            "go": go,
            "stats": __import__("scipy.stats").stats,
            "df": self.df,
        }

    def _get_chatbot(self) -> PythonChatbot:
        if self.user_id not in _chatbots:
            _chatbots[self.user_id] = PythonChatbot()
        return _chatbots[self.user_id]

    def load_history(self, session_id: int = None):
        """Charge l'historique des messages depuis la base de données pour un utilisateur/session."""
        if self.db is None:
            return []
        query = self.db.query(ChatMessage).filter(ChatMessage.user_id == self.user_id)
        if session_id:
            query = query.filter(ChatMessage.session_id == session_id)
        messages = query.order_by(ChatMessage.created_at.asc()).all()

        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": str(msg.created_at) if msg.created_at else "",
                "intermediate_outputs": msg.intermediate_outputs,
            }
            for msg in messages
        ]

    def _save_message(self, role: str, content: str, intermediate_outputs: dict = None):
        """Sauvegarde un message (utilisateur ou assistant) dans l'historique de la base de données."""
        if self.db is None:
            return None
        new_msg = ChatMessage(
            user_id=self.user_id,
            role=role,
            content=content,
            intermediate_outputs=intermediate_outputs,
        )
        self.db.add(new_msg)
        self.db.commit()
        self.db.refresh(new_msg)
        return new_msg

    def _save_to_db(self, role: str, content: str, intermediate_outputs: dict = None):
        """Alias interne pour la rétrocompatibilité"""
        return self._save_message(role, content, intermediate_outputs)

    @staticmethod
    def _figure_to_json(fig: go.Figure) -> dict:
        """Serialize a Plotly figure without version-incompatible template traces."""
        fig_json = json.loads(fig.to_json())
        layout = fig_json.get("layout")
        if isinstance(layout, dict):
            layout.pop("template", None)
        return fig_json

    @staticmethod
    def _load_figure_json(image_paths: List[str]) -> Optional[dict]:
        pickle_dir = os.path.abspath("images/plotly_figures/pickle")
        for name in reversed(list(image_paths or [])):
            path = name if os.path.isabs(name) else os.path.join(pickle_dir, name)
            if not os.path.exists(path):
                continue
            try:
                with open(path, "rb") as f:
                    fig = pickle.load(f)
                if isinstance(fig, go.Figure):
                    return AgentManager._figure_to_json(fig)
            except Exception:
                continue
        return None

    def _resolve_input_data(
        self, df: Optional[pd.DataFrame] = None, input_data: Optional[List[InputData]] = None
    ) -> List[InputData]:
        if input_data:
            return input_data

        active_df = df if df is not None else self.df
        if active_df is not None:
            os.makedirs(dataset_store.UPLOAD_ROOT, exist_ok=True)
            tmp = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".csv",
                dir=dataset_store.UPLOAD_ROOT,
                prefix=f"user_{self.user_id}_",
            )
            active_df.to_csv(tmp.name, index=False)
            tmp.close()
            item = InputData(
                variable_name="df",
                data_path=os.path.abspath(tmp.name),
                data_description="DataFrame fourni pour l'analyse",
            )
            if self.user_id is not None:
                dataset_store.set_primary_dataset(self.user_id, item)
            return [item]

        datasets = dataset_store.get_datasets(self.user_id)
        if datasets:
            return datasets

        return []

    def _run_analysis(self, query: str, input_data: List[InputData]) -> dict:
        if not input_data:
            return {
                "status": "error",
                "output": "Aucun dataset chargé. Importez un CSV avant de poser une question.",
                "fig": None,
            }

        chatbot = self._get_chatbot()
        result = chatbot.run_query(query, input_data)
        fig_json = self._load_figure_json(result.get("image_paths", []))

        output = (result.get("output") or "").strip()
        if PythonChatbot._is_echo_or_empty(output, query):
            for item in result.get("intermediate_outputs") or []:
                if isinstance(item, dict) and item.get("output"):
                    candidate = str(item["output"]).strip()
                    if not PythonChatbot._is_echo_or_empty(candidate, query):
                        output = candidate
                        break

        return {
            "status": "success",
            "output": output
            or "Analyse exécutée, mais aucune sortie textuelle n'a été capturée.",
            "fig": fig_json,
            "figure": fig_json,
            "intermediate_outputs": result.get("intermediate_outputs", []),
        }

    async def ask(
        self,
        query: str,
        df: Optional[pd.DataFrame] = None,
        input_data: Optional[List[InputData]] = None,
        persist: bool = True,
    ) -> dict:
        """Run the real LangGraph ReAct agent on the loaded dataset."""
        resolved = self._resolve_input_data(df=df, input_data=input_data)
        if persist:
            self._save_message("user", query)

        try:
            result = await asyncio.to_thread(self._run_analysis, query, resolved)
        except Exception as e:
            result = {
                "status": "error",
                "output": f"Erreur lors de l'analyse : {e}",
                "message": str(e),
                "fig": None,
            }

        if persist:
            self._save_message(
                "assistant",
                result.get("output") or result.get("message") or "",
                {
                    "type": "agent",
                    "status": result.get("status"),
                    "fig": result.get("fig"),
                    "intermediate_outputs": result.get("intermediate_outputs"),
                },
            )
        return result

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
                        fig_json = self._figure_to_json(var)
                        break

                output = stdout_capture.getvalue().strip()
                if not output:
                    output = (
                        "Code exécuté avec succès."
                        if fig_json
                        else "Code exécuté, mais aucune sortie print() n'a été produite."
                    )
                self._save_message("assistant", output, {"type": "viz", "data": fig_json})
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

                if "df" in local_vars and isinstance(local_vars["df"], pd.DataFrame):
                    self.df = local_vars["df"]
                    self.globals["df"] = self.df

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
