import streamlit as st
import plotly.graph_objects as go
from utils.api_client import APIClient  # Utilise ton fichier actuel

st.set_page_config(page_title="DataStream AI", layout="wide")

# --- Initialisation de l'état (Partie 3.2) ---
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None

# --- UI d'Authentification (Partie 3.2 : 1 point) ---
if not st.session_state.token:
    st.title("🔐 Connexion à la Plateforme")
    
    with st.form("login_form"):
        u = st.text_input("Utilisateur")
        p = st.text_input("Mot de passe", type="password")
        submit = st.form_submit_button("Se connecter")
        
        if submit:
            if APIClient.login(u, p):
                st.success("Connecté !")
                st.rerun()
            else:
                st.error("Identifiants invalides ou serveur hors ligne")
else:
    # --- Sidebar & Historique (Partie 3.3 : 2 points) ---
    st.sidebar.title(f"👤 {st.session_state.username}")
    
    if st.sidebar.button("Déconnexion"):
        st.session_state.token = None
        st.rerun()
    
    st.sidebar.divider()
    st.sidebar.subheader("📜 Sessions passées")
    
    # Récupération de l'historique via ton api_client.py
    history = APIClient.get_history()
    
    if history:
        for msg in history:
            # On affiche la date comme nom de session
            date_label = msg.get("created_at", "Session")[:16].replace("T", " ")
            if st.sidebar.button(f"📅 {date_label}", key=f"hist_{msg['id']}"):
                st.info(f"Chargement de la session du {date_label}...")
                # Ici on pourrait filtrer l'affichage pour ne montrer que ce message
    else:
        st.sidebar.write("Aucun historique trouvé.")

    # --- Zone de Chat principale ---
    st.title("🤖 Assistant d'Analyse")
    
    query = st.chat_input("Analysez vos données...")
    
    if query:
        with st.chat_message("user"):
            st.write(query)
            
        with st.spinner("L'agent génère la réponse..."):
            # Appel à ton API via l'agent ReAct
            response = APIClient.ask_agent(query)
            
            with st.chat_message("assistant"):
                st.write(response.get("output", "Analyse terminée."))
                
                # Restauration automatique du graphique Plotly (Partie 3.3)
                if response.get("fig"):
                    fig = go.Figure(response["fig"])
                    st.plotly_chart(fig)
