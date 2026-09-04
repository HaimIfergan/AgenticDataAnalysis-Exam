from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from typing import List
from langgraph.graph import StateGraph
from Pages.graph.state import AgentState
from Pages.graph.nodes import call_model, call_tools, route_to_tools
from Pages.data_models import InputData


class PythonChatbot:
    def __init__(self):
        self.reset_chat()
        self.graph = self.create_graph()

    def create_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", call_tools)

        workflow.add_conditional_edges("agent", route_to_tools)

        workflow.add_edge("tools", "agent")
        workflow.set_entry_point("agent")
        return workflow.compile()

    def run_query(self, user_query: str, input_data: List[InputData]) -> dict:
        """Invoke the ReAct graph and return real analysis text + figure paths."""
        starting_image_paths_set = set(sum(self.output_image_paths.values(), []))
        input_state = {
            "messages": self.chat_history + [HumanMessage(content=user_query)],
            "output_image_paths": list(starting_image_paths_set),
            "input_data": input_data,
        }

        result = self.graph.invoke(input_state, {"recursion_limit": 25})
        self.chat_history = result["messages"]
        new_image_paths = set(result.get("output_image_paths", [])) - starting_image_paths_set
        self.output_image_paths[len(self.chat_history) - 1] = list(new_image_paths)

        intermediate = result.get("intermediate_outputs", []) or []
        if intermediate:
            self.intermediate_outputs.extend(intermediate)

        output_text = self._compose_output(
            user_query=user_query,
            messages=result.get("messages", []),
            intermediate_outputs=intermediate,
        )

        return {
            "output": output_text,
            "image_paths": list(new_image_paths),
            "intermediate_outputs": intermediate,
            "messages": result.get("messages", []),
        }

    def user_sent_message(self, user_query, input_data: List[InputData]):
        return self.run_query(user_query, input_data)

    @staticmethod
    def _message_text(message) -> str:
        content = getattr(message, "content", "") or ""
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            content = "".join(parts)
        return str(content).strip()

    @classmethod
    def _extract_assistant_text(cls, messages) -> str:
        """Last final AI answer (skip tool-calling turns)."""
        for message in reversed(messages or []):
            if not isinstance(message, AIMessage):
                continue
            if getattr(message, "tool_calls", None):
                continue
            text = cls._message_text(message)
            if text:
                return text
        return ""

    @classmethod
    def _collect_tool_stdout(cls, messages, intermediate_outputs) -> List[str]:
        """Real Python execution output from tools / ToolMessages."""
        outputs: List[str] = []
        for item in intermediate_outputs or []:
            if isinstance(item, dict):
                out = str(item.get("output") or "").strip()
                if out:
                    outputs.append(out)
        if not outputs:
            for message in messages or []:
                if isinstance(message, ToolMessage):
                    text = cls._message_text(message)
                    if text:
                        outputs.append(text)
        return outputs

    @staticmethod
    def _is_echo_or_empty(text: str, query: str) -> bool:
        t = (text or "").strip()
        if not t:
            return True
        q = (query or "").strip()
        low = t.lower()
        if q and t == q:
            return True
        if q and low in {q.lower(), f"analyse demandée : {q}".lower()}:
            return True
        if low.startswith("analyse demandée"):
            return True
        return False

    @classmethod
    def _compose_output(cls, user_query: str, messages, intermediate_outputs) -> str:
        """
        Prefer raw Python stdout from tool execution.
        Never return an empty string or a hardcoded echo of the user question.
        """
        query = (user_query or "").strip()
        assistant = cls._extract_assistant_text(messages)
        tool_outputs = cls._collect_tool_stdout(messages, intermediate_outputs)
        joined_tools = "\n".join(tool_outputs).strip()

        if joined_tools and not cls._is_echo_or_empty(joined_tools, query):
            return joined_tools

        if assistant and not cls._is_echo_or_empty(assistant, query):
            return assistant

        for item in reversed(intermediate_outputs or []):
            if isinstance(item, dict):
                thought = str(item.get("thought") or "").strip()
                if thought and not cls._is_echo_or_empty(thought, query):
                    return thought

        return (
            "Analyse exécutée, mais aucune sortie textuelle n'a été capturée. "
            "Le code doit utiliser print() pour afficher le résultat."
        )

    def reset_chat(self):
        self.chat_history = []
        self.intermediate_outputs = []
        self.output_image_paths = {}
