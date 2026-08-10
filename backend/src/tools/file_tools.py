import os

from langchain_core.tools import tool

WORKSPACE = os.environ.get("WORKSPACE_DIR", "workspace")


@tool
def read_file(path: str) -> str:
    """Read a file from the workspace directory."""
    try:
        full_path = os.path.join(WORKSPACE, os.path.basename(path))
        with open(full_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "Error: File not found"
    except Exception as e:
        return f"Error: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file in the workspace directory."""
    try:
        os.makedirs(WORKSPACE, exist_ok=True)
        full_path = os.path.join(WORKSPACE, os.path.basename(path))
        with open(full_path, "w") as f:
            f.write(content)
        return f"File written successfully: {full_path}"
    except Exception as e:
        return f"Error: {e}"
