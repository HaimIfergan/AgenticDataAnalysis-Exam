from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL

from langchain_core.messages import AIMessage
from typing import Annotated, Tuple
from langgraph.prebuilt import InjectedState
import sys
from io import StringIO
import os
import plotly.graph_objects as go
import plotly.io as pio
import plotly.express as px
import pandas as pd
import sklearn


repl = PythonREPL()

persistent_vars = {}
plotly_saving_code = """import pickle
import uuid
import plotly

for figure in plotly_figures:
    pickle_filename = f"images/plotly_figures/pickle/{uuid.uuid4()}.pickle"
    with open(pickle_filename, 'wb') as f:
        pickle.dump(figure, f)
"""

@tool(parse_docstring=True)
def complete_python_task(
        graph_state: Annotated[dict, InjectedState], thought: str, python_code: str
) -> Tuple[str, dict]:
    """Completes a python task

    Args:
        thought: Internal thought about the next action to be taken, and the reasoning behind it. This should be formatted in MARKDOWN and be high quality.
        python_code: Python code to be executed to perform analyses, create a new dataset or create a visualization.
    """
    current_variables = graph_state["current_variables"] if "current_variables" in graph_state else {}
    last_loaded = None
    for input_dataset in graph_state["input_data"]:
        if input_dataset.variable_name not in current_variables:
            loaded = pd.read_csv(input_dataset.data_path)
            current_variables[input_dataset.variable_name] = loaded
            last_loaded = loaded
        else:
            last_loaded = current_variables[input_dataset.variable_name]
    # Always expose the latest CSV as `df` for simple user questions
    if last_loaded is not None and "df" not in current_variables:
        current_variables["df"] = last_loaded
    if not os.path.exists("images/plotly_figures/pickle"):
        os.makedirs("images/plotly_figures/pickle")

    current_image_pickle_files = os.listdir("images/plotly_figures/pickle")
    old_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        exec_globals = globals().copy()
        exec_globals.update(persistent_vars)
        exec_globals.update(current_variables)
        exec_globals.update({"plotly_figures": []})

        exec(python_code, exec_globals)
        persistent_vars.update({k: v for k, v in exec_globals.items() if k not in globals()})

        # Capture figures even if the LLM forgot plotly_figures.append
        figures = list(exec_globals.get("plotly_figures") or [])
        for value in exec_globals.values():
            if isinstance(value, go.Figure) and value not in figures:
                figures.append(value)
        exec_globals["plotly_figures"] = figures

        output = sys.stdout.getvalue().strip()
        # Always give the LLM something concrete to summarize (never empty)
        if not output:
            if figures:
                output = "Code exécuté avec succès. Graphique Plotly généré."
            else:
                output = (
                    "Code exécuté avec succès, mais aucune sortie print() n'a été produite. "
                    "Réaffiche le résultat avec print()."
                )

        updated_state = {
            "intermediate_outputs": [{"thought": thought, "code": python_code, "output": output}],
            "current_variables": persistent_vars,
        }

        if figures:
            exec(plotly_saving_code, exec_globals)
            new_image_folder_contents = os.listdir("images/plotly_figures/pickle")
            new_image_files = [
                file for file in new_image_folder_contents if file not in current_image_pickle_files
            ]
            if new_image_files:
                updated_state["output_image_paths"] = new_image_files
            persistent_vars["plotly_figures"] = []

        return output, updated_state
    except Exception as e:
        error_text = f"Erreur d'exécution Python : {e}"
        return error_text, {
            "intermediate_outputs": [{"thought": thought, "code": python_code, "output": error_text}]
        }
    finally:
        sys.stdout = old_stdout
