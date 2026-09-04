import streamlit as st
import pandas as pd
import os
import json
import pickle
from langchain_core.messages import HumanMessage, AIMessage
from Pages.backend import PythonChatbot, InputData

# 1. Dossiers
UPLOAD_DIR = "uploads"
PICKLE_DIR = "images/plotly_figures/pickle"
for d in [UPLOAD_DIR, PICKLE_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

st.title("Data Analysis Dashboard")

# 2. Data Dict
try:
    with open('data_dictionary.json', 'r') as f:
        data_dictionary = json.load(f)
except:
    data_dictionary = {}

t1, t2, t3 = st.tabs(["Data Management", "Chat Interface", "Debug"])

with t1:
    up = st.file_uploader("Upload CSV", type="csv", accept_multiple_files=True)
    if up:
        for f in up:
            with open(os.path.join(UPLOAD_DIR, f.name), "wb") as file:
                file.write(f.getbuffer())
        st.success("Upload OK")

with t2:
    if 'visualisation_chatbot' not in st.session_state:
        st.session_state.visualisation_chatbot = PythonChatbot()

    def handle_query():
        q = st.session_state.user_input
        inputs = [InputData(variable_name=f.split('.')[0], 
                  data_path=os.path.abspath(os.path.join(UPLOAD_DIR, f)),
                  data_description=data_dictionary.get(f, {}).get('description', '')) 
                  for f in st.session_state.get('selected_files', [])]
        st.session_state.visualisation_chatbot.user_sent_message(q, input_data=inputs)

    # Affichage
    c = st.container(height=500)
    with c:
        for msg in st.session_state.visualisation_chatbot.chat_history:
            if isinstance(msg, HumanMessage):
                st.chat_message("user").write(msg.content)
            else:
                with st.chat_message("assistant"):
                    st.write(msg.content)
                    # Scan des fichiers pickles
                    if os.path.exists(PICKLE_DIR):
                        for i, f_name in enumerate(os.listdir(PICKLE_DIR)):
                            if f_name.endswith(".pickle"):
                                with open(os.path.join(PICKLE_DIR, f_name), "rb") as f:
                                    fig = pickle.load(f)
                                st.plotly_chart(fig, key=f"plot_{i}_{f_name}")

    st.chat_input("Ta question ?", key="user_input", on_submit=handle_query)

with t3:
    if st.button("Reset Chat"):
        st.session_state.visualisation_chatbot.reset_chat()
        st.rerun()