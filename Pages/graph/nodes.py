from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from .state import AgentState
from .tools import complete_python_task
from typing import Literal
import os
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY"),
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
    merged_state = {}
    for tool_call in last_message.tool_calls:
        # Exécution réelle du code Python sur le DataFrame
        raw = complete_python_task.invoke(
            {**tool_call["args"], "graph_state": state}
        )
        # Le tool renvoie (stdout, updated_state)
        if isinstance(raw, tuple) and len(raw) == 2:
            result, updated_state = raw
        else:
            result, updated_state = raw, {}

        tool_messages.append(
            ToolMessage(
                content=str(result) if result is not None else "",
                tool_call_id=tool_call["id"],
                name=tool_call.get("name", "complete_python_task"),
            )
        )
        if isinstance(updated_state, dict):
            for key, value in updated_state.items():
                if key in ("intermediate_outputs", "output_image_paths") and key in merged_state:
                    merged_state[key] = list(merged_state[key]) + list(value)
                else:
                    merged_state[key] = value
    return {"messages": tool_messages, **merged_state}