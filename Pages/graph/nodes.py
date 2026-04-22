from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from .state import AgentState
from .tools import complete_python_task
from typing import Literal
import os

# Dans Pages/graph/nodes.py à la ligne 9 :
llm = ChatOpenAI(
    model="gpt-4o-mini", 
    temperature=0, 
    api_key="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" # Remets ta clé ici
)
tools = [complete_python_task]
model = llm.bind_tools(tools)

# Chargement du prompt (assure-toi que le fichier existe dans Pages/prompts/)
with open(os.path.join(os.path.dirname(__file__), "../prompts/main_prompt.md"), "r") as file:
    prompt_content = file.read()

chat_template = ChatPromptTemplate.from_messages([
    ("system", prompt_content),
    ("placeholder", "{messages}"),
])
model = chat_template | model

def route_to_tools(state: AgentState) -> Literal["tools", "__end__"]:
    messages = state.get("messages", [])
    if not messages:
        return "__end__"
    
    last_message = messages[-1]
    
    # CONDITION STRICTE : 
    # On ne va vers "tools" QUE si l'IA a généré des appels d'outils REELS
    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        # Optionnel : log pour debugger dans ton terminal
        print(f"--- ROUTAGE : OUTIL DÉTECTÉ ({last_message.tool_calls[0]['name']}) ---")
        return "tools"
    
    # Dans tous les autres cas (texte simple, fin de réflexion), on s'arrête.
    print("--- ROUTAGE : FIN DU GRAPHE ---")
    return "__end__"

def call_model(state: AgentState):
    # Résumé des données pour le SystemMessage
    summary = ""
    for d in state["input_data"]:
        summary += f"\nVariable: {d.variable_name}\nDescription: {d.data_description}"
    
    system_info = SystemMessage(content=f"Available data: {summary}")
    
    # Appel du modèle avec l'historique complet
    response = model.invoke({"messages": [system_info] + state["messages"]})
    return {"messages": [response]}

def call_tools(state: AgentState):
    last_message = state["messages"][-1]
    tool_messages = []
    for tool_call in last_message.tool_calls:
        # Exécution de l'outil Python
        result, _ = complete_python_task.invoke({**tool_call["args"], "graph_state": state})
        tool_messages.append(ToolMessage(
            content=str(result), 
            tool_call_id=tool_call["id"], 
            name=tool_call["name"]
        ))
    return {"messages": tool_messages}