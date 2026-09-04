import copy
import streamlit as st
import plotly.graph_objects as go
from utils.api_client import APIClient

_MAPBOX_TRACE_RENAMES = {
    "scattermapbox": "scattermap",
    "choroplethmapbox": "choroplethmap",
    "densitymapbox": "densitymap",
}


def _sanitize_plotly_payload(obj):
    """Align Plotly 5 mapbox traces/templates with Plotly 6 names."""
    if isinstance(obj, dict):
        if obj.get("type") in _MAPBOX_TRACE_RENAMES:
            obj["type"] = _MAPBOX_TRACE_RENAMES[obj["type"]]
        for old, new in _MAPBOX_TRACE_RENAMES.items():
            if old in obj:
                if new not in obj:
                    obj[new] = obj.pop(old)
                else:
                    obj.pop(old)
        if "mapbox" in obj:
            if "map" not in obj:
                obj["map"] = obj.pop("mapbox")
            else:
                obj.pop("mapbox")
        for value in list(obj.values()):
            _sanitize_plotly_payload(value)
    elif isinstance(obj, list):
        for item in obj:
            _sanitize_plotly_payload(item)


def figure_from_payload(fig_data):
    payload = copy.deepcopy(fig_data)
    _sanitize_plotly_payload(payload)
    try:
        return go.Figure(payload)
    except ValueError:
        if isinstance(payload, dict) and isinstance(payload.get("layout"), dict):
            payload["layout"].pop("template", None)
        return go.Figure(payload)


def render_plotly_chart(fig_data, key: str):
    try:
        st.plotly_chart(figure_from_payload(fig_data), key=key)
    except Exception as e:
        st.error(f"Erreur d'affichage du graphique : {e}")

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
        st.session_state.uploaded_file = uploaded_file
        if st.session_state.get("uploaded_file_name") != uploaded_file.name:
            with st.spinner("Transmission du fichier au serveur..."):
                uploaded_file.seek(0)
                success = APIClient.upload_file(uploaded_file)
                if success:
                    st.sidebar.success(f"Fichier '{uploaded_file.name}' chargé et transmis !")
                    st.session_state.uploaded_file_name = uploaded_file.name
                    if isinstance(success, dict) and success.get("columns"):
                        st.sidebar.caption("Colonnes : " + ", ".join(map(str, success["columns"])))
                else:
                    st.sidebar.error("Erreur lors de l'envoi du fichier au backend.")
        elif st.session_state.get("uploaded_file_name") == uploaded_file.name:
            st.sidebar.caption(f"Dataset actif : {uploaded_file.name}")

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
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            # Affichage du JSON brut si disponible pour le débug
            if "raw" in message:
                with st.expander("🔍 Voir le JSON brut reçu du backend"):
                    st.json(message["raw"])
            if message.get("fig"):
                render_plotly_chart(message["fig"], key=f"plot_hist_{i}")

    # Saisie utilisateur
    query = st.chat_input("Analysez vos données...")
    
    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.write(query)
            
        with st.spinner("L'agent analyse les données..."):
            response = APIClient.ask_agent(
                query,
                file_obj=st.session_state.get("uploaded_file"),
            )
            
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
                    render_plotly_chart(
                        fig_data,
                        key=f"plot_live_{len(st.session_state.messages) - 1}",
                    )