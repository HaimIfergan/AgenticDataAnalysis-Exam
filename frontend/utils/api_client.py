import os
import requests
import streamlit as st

# Utilise la variable d'environnement API_URL (définie dans Docker), ou localhost par défaut[cite: 1]
BASE_URL = os.getenv("API_URL", "http://localhost:8000")

class APIClient:
    @staticmethod
    def login(username, password):
        """3.1 & 3.2: Gère l'authentification et stocke le JWT"""
        try:
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                data={
                    "username": username, 
                    "password": password,
                    "grant_type": "password"  # Ajouté pour valider le formulaire OAuth2 FastAPI
                },
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
        response = requests.get(f"{BASE_URL}/api/chat/history/1", headers=headers)
        return response.json() if response.status_code == 200 else []

    @staticmethod
    def ask_agent(query):
        """Consomme l'agent ReAct de manière sécurisée"""
        try:
            headers = {"Authorization": f"Bearer {st.session_state.get('token')}"}
            params = {"user_id": 1, "query": query}
            
            # Timeout de 30s pour laisser le temps à l'agent d'analyser les données
            response = requests.post(f"{BASE_URL}/api/chat/ask", params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    return data
                return {"output": str(data), "fig": None}
            else:
                return {
                    "output": f"⚠️ Erreur serveur ({response.status_code}) : {response.text}",
                    "fig": None
                }
        except Exception as e:
            return {
                "output": f"❌ Erreur de communication avec l'agent : {str(e)}",
                "fig": None
            }

    @staticmethod
    def upload_file(file_obj):
        """Envoie un fichier vers l'API Backend"""
        try:
            headers = {"Authorization": f"Bearer {st.session_state.get('token')}"}
            files = {"file": (file_obj.name, file_obj.getvalue(), file_obj.type)}
            
            response = requests.post(
                f"{BASE_URL}/api/upload", 
                headers=headers,
                files=files,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Erreur serveur ({response.status_code}) : {response.text}"}
        except Exception as e:
            return {"error": f"Erreur de communication : {str(e)}"}