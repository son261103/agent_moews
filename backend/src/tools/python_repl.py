import io
import sys
import threading

from langchain_core.tools import tool


@tool
def python_repl(code: str) -> str:
    """Execute Python code in a sandboxed environment with 30s timeout."""
    timed_out = False

    def timeout_handler():
        nonlocal timed_out
        timed_out = True

    timer = threading.Timer(30.0, timeout_handler)
    timer.start()
    try:
        stdout = io.StringIO()
        stderr = io.StringIO()
        sys.stdout = stdout
        sys.stderr = stderr
        try:
            exec(code, {"__builtins__": __builtins__})
        finally:
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__

        if timed_out:
            return "Error: Code execution timed out after 30 seconds"

        output = stdout.getvalue()
        error = stderr.getvalue()
        if error:
            return f"{output}\nStderr: {error}" if output else error
        return output if output else "Code executed successfully (no output)"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
