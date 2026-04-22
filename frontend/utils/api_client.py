import requests
import streamlit as st

BASE_URL = "http://localhost:8000"

class APIClient:
    @staticmethod
    def login(username, password):
        """3.1 & 3.2: Gère l'authentification et stocke le JWT"""
        try:
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                data={"username": username, "password": password},
                timeout=5
            )
            if response.status_code == 200:
                st.session_state.token = response.json().get("access_token")
                st.session_state.username = username
                return True
            return False
        except requests.exceptions.ConnectionError:
            st.error("❌ Impossible de contacter le Backend (FastAPI). Est-il lancé ?")
            return False

    @staticmethod
    def get_history():
        """3.3: Récupère l'historique depuis la DB"""
        if not st.session_state.get("token"):
            return []
        
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        # On utilise l'ID 1 pour le test comme configuré dans ton main.py
        response = requests.get(f"{BASE_URL}/api/chat/history/1", headers=headers)
        return response.json() if response.status_code == 200 else []

    @staticmethod
    def ask_agent(query):
        """Consomme l'agent ReAct"""
        headers = {"Authorization": f"Bearer {st.session_state.get('token')}"}
        params = {"user_id": 1, "query": query}
        response = requests.post(f"{BASE_URL}/api/chat/ask", params=params, headers=headers)
        return response.json()
