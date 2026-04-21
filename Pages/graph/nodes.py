from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
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
    current_data_template = "The following data is available:\n{data_summary}"
    current_data_message = HumanMessage(content=current_data_template.format(data_summary=create_data_summary(state)))
    
    # On ajoute le résumé des données au contexte
    response = model.invoke({**state, "messages": [current_data_message] + state["messages"]})
    return {"messages": [response], "intermediate_outputs": [current_data_message.content]}

def call_model(state: AgentState):
    # On prépare le résumé des données
    data_summary = create_data_summary(state)
    current_data_template = "The following data is available:\n{data_summary}"
    
    # IMPORTANT : On ne modifie PAS state["messages"] directement ici pour éviter les doublons
    # On injecte l'information système de manière ponctuelle pour l'appel au modèle
    system_context = HumanMessage(content=current_data_template.format(data_summary=data_summary))
    
    # On appelle le modèle avec le contexte des données + l'historique
    response = model.invoke({
        **state, 
        "messages": [system_context] + state["messages"]
    })

    # On ne retourne que le nouveau message de l'IA
    return {
        "messages": [response], 
        "intermediate_outputs": [system_context.content]
    }