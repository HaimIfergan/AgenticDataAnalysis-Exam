from langchain_openai import ChatOpenAI
# AJOUT DE SystemMessage ICI
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from .state import AgentState
import json
from typing import Literal
from .tools import complete_python_task
import os

# Configuration du LLM
llm = ChatOpenAI(
    model="gpt-4o-mini", 
    temperature=0, 
    api_key="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"
)

tools = [complete_python_task]
model = llm.bind_tools(tools)

# Chargement du prompt
with open(os.path.join(os.path.dirname(__file__), "../prompts/main_prompt.md"), "r") as file:
    prompt = file.read()

chat_template = ChatPromptTemplate.from_messages([
    ("system", prompt),
    ("placeholder", "{messages}"),
])
model = chat_template | model

def create_data_summary(state: AgentState) -> str:
    summary = ""
    variables = []
    for d in state["input_data"]:
        variables.append(d.variable_name)
        summary += f"\n\nVariable: {d.variable_name}\n"
        summary += f"Description: {d.data_description}"
    
    if "current_variables" in state:
        remaining_variables = [v for v in state["current_variables"] if v not in variables]
        for v in remaining_variables:
            summary += f"\n\nVariable: {v}"
    return summary

def route_to_tools(state: AgentState) -> Literal["tools", "__end__"]:
    if messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state: {state}")
    
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"
    return "__end__"

def call_model(state: AgentState):
    """
    Appelle le modèle avec le dictionnaire attendu par ChatPromptTemplate.
    """
    data_summary = create_data_summary(state)
    
    # Message système pour injecter les données sans polluer l'historique permanent
    system_data_info = SystemMessage(
        content=f"The following data is available:\n{data_summary}"
    )
    
    # On passe un dictionnaire avec la clé 'messages' demandée par le template
    response = model.invoke({
        "messages": [system_data_info] + state["messages"]
    })

    return {
        "messages": [response],
        "intermediate_outputs": [system_data_info.content]
    }

def call_tools(state: AgentState):
    """
    Exécution manuelle pour éviter le bug 'No message found in input'.
    """
    last_message = state["messages"][-1]
    tool_messages = []

    if hasattr(last_message, "tool_calls"):
        for tool_call in last_message.tool_calls:
            # On appelle l'outil avec .invoke()
            result, updates = complete_python_task.invoke({
                **tool_call["args"], 
                "graph_state": state
            })
            
            # On crée le ToolMessage obligatoire pour valider l'étape
            tool_messages.append(ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
                name=tool_call["name"]
            ))

    return {"messages": tool_messages}