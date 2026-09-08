import ast
from pathlib import Path
from typing import List, Tuple

def strip_hallucinated_endpoint(project_dir: Path, target_name: str) -> bool:
    """
    Search the project for an endpoint or command matching `target_name`.
    If found, safely remove its AST node (function definition) from the source code.
    Returns True if successfully removed, False otherwise.
    """
    for file_path in project_dir.rglob("*.py"):
        if ".venv" in file_path.parts or "node_modules" in file_path.parts:
            continue
            
        try:
            source = file_path.read_text()
            tree = ast.parse(source, filename=str(file_path))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check decorators
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        # e.g., @app.get("/api/scan") or @cli.command("add")
                        if hasattr(decorator.func, "attr") and decorator.func.attr in ("get", "post", "put", "delete", "patch", "command", "add_parser"):
                            if decorator.args and hasattr(decorator.args[0], "value"):
                                arg_val = decorator.args[0].value
                                if arg_val == target_name:
                                    _remove_lines(file_path, source, node.lineno, node.end_lineno)
                                    return True
                        elif hasattr(decorator.func, "id") and decorator.func.id == "command":
                            # e.g., @command() def add(): ...
                            if node.name == target_name:
                                _remove_lines(file_path, source, node.lineno, node.end_lineno)
                                return True
    return False

def _remove_lines(file_path: Path, source: str, start_line: int, end_line: int):
    lines = source.splitlines()
    # Lines are 1-indexed in AST
    del lines[start_line - 1 : end_line]
    file_path.write_text("\n".join(lines) + "\n")
