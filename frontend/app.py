import streamlit as st
import plotly.graph_objects as go
from utils.api_client import APIClient

st.set_page_config(page_title="DataStream AI", layout="wide")

# --- Initialisation de l'état ---
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None

# --- UI d'Authentification ---
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
    # --- Sidebar & Gestion des données ---
    st.sidebar.title(f"👤 {st.session_state.username}")
    
    if st.sidebar.button("Déconnexion"):
        st.session_state.token = None
        st.rerun()
    
    st.sidebar.divider()
    
    # --- Upload et transmission du fichier au Backend ---
    st.sidebar.subheader("📁 Données")
    uploaded_file = st.sidebar.file_uploader("Importer un fichier (CSV, Excel)", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        if st.session_state.get("uploaded_file_name") != uploaded_file.name:
            with st.spinner("Transmission du fichier au serveur..."):
                success = APIClient.upload_file(uploaded_file)
                if success:
                    st.sidebar.success(f"Fichier '{uploaded_file.name}' chargé et transmis !")
                    st.session_state.uploaded_file_name = uploaded_file.name
                else:
                    st.sidebar.error("Erreur lors de l'envoi du fichier au backend.")

    st.sidebar.divider()
    st.sidebar.subheader("📜 Sessions passées")
    
    history = APIClient.get_history()
    
    if history:
        for i, msg in enumerate(history):
            date_label = msg.get("created_at", "Session")[:16].replace("T", " ")
            msg_id = msg.get("id", i)
            if st.sidebar.button(f"📅 {date_label}", key=f"hist_{msg_id}_{i}"):
                st.info(f"Chargement de la session du {date_label}...")
    else:
        st.sidebar.write("Aucun historique trouvé.")

    # --- Zone de Chat principale ---
    st.title("🤖 Assistant d'Analyse")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Affichage de l'historique des messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            # Affichage du JSON brut si disponible pour le débug
            if "raw" in message:
                with st.expander("🔍 Voir le JSON brut reçu du backend"):
                    st.json(message["raw"])
            if message.get("fig"):
                try:
                    st.plotly_chart(go.Figure(message["fig"]))
                except Exception:
                    pass

    # Saisie utilisateur
    query = st.chat_input("Analysez vos données...")
    
    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.write(query)
            
        with st.spinner("L'agent analyse les données..."):
            response = APIClient.ask_agent(query)
            
            # Analyse robuste de la réponse
            output_text = None
            fig_data = None
            
            if isinstance(response, dict):
                output_text = (
                    response.get("output") or 
                    response.get("response") or 
                    response.get("result") or 
                    response.get("message") or
                    response.get("text")
                )
                fig_data = response.get("fig") or response.get("figure")
            else:
                output_text = str(response)
            
            if not output_text:
                output_text = "⚠️ Le backend a répondu, mais le champ texte est vide."
            
            assistant_msg = {
                "role": "assistant",
                "content": output_text,
                "fig": fig_data,
                "raw": response  # Sauvegarde pour l'expander de debug
            }
            st.session_state.messages.append(assistant_msg)
            
            with st.chat_message("assistant"):
                st.write(output_text)
                with st.expander("🔍 Voir le JSON brut reçu du backend"):
                    st.json(response)
                if fig_data:
                    try:
                        st.plotly_chart(go.Figure(fig_data))
                    except Exception as e:
                        st.error(f"Erreur d'affichage du graphique : {e}")