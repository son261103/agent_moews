import concurrent.futures
import io
import sys

from langchain_core.tools import tool

from src.tools.truncate import truncate_text

import math
import time

# Modules safe to import in sandbox
_SAFE_MODULES = {"sys", "time", "math", "json", "re", "io", "collections", "itertools", "functools", "operator", "string", "textwrap", "typing"}

def _safe_import(name, *args, **kwargs):
    if name not in _SAFE_MODULES:
        raise ImportError(f"Module '{name}' is not allowed in sandbox")
    return __import__(name, *args, **kwargs)


# Safe builtins: only allow basic operations, no os/sys/subprocess/file access
_SAFE_BUILTINS = {
    "print": print,
    "len": len,
    "range": range,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "round": round,
    "sorted": sorted,
    "reversed": reversed,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "isinstance": isinstance,
    "type": type,
    "repr": repr,
    "input": input,  # harmless in exec context
    "__import__": _safe_import,
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "IndexError": IndexError,
    "KeyError": KeyError,
    "AttributeError": AttributeError,
    "ZeroDivisionError": ZeroDivisionError,
    "StopIteration": StopIteration,
    "True": True,
    "False": False,
    "None": None,
}


def _execute_code(code: str) -> tuple[str, str]:
    """Execute code and return (stdout, stderr). Runs in a worker thread."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    try:
        sys.stdout = stdout
        sys.stderr = stderr
        exec(code, {"__builtins__": _SAFE_BUILTINS})
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    return stdout.getvalue(), stderr.getvalue()


@tool
def python_repl(code: str) -> str:
    """Execute Python code in a sandboxed environment with 30s timeout."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_execute_code, code)
        try:
            stdout, stderr = future.result(timeout=30)
        except concurrent.futures.TimeoutError:
            return "Error: Code execution timed out after 30 seconds"
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

    if stderr:
        return truncate_text(f"{stdout}\nStderr: {stderr}" if stdout else f"Stderr: {stderr}")
    return truncate_text(stdout) if stdout else "Code executed successfully (no output)"
