"""Static guards for the login: passwords never reach a log, and only the login
code decides who is logged in."""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOGIN_FILES = ["app.py", "core/auth.py", "services/auth.py", "integrations/db.py", "scripts/reset_password.py"]


def parse(relative_path):
    return ast.parse((REPO_ROOT / relative_path).read_text(encoding="utf-8"))


def names_in(node):
    """Every variable, attribute and string mentioned inside a node, lower-cased."""
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            yield child.id.lower()
        elif isinstance(child, ast.Attribute):
            yield child.attr.lower()
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            yield child.value.lower()


def logging_calls(tree):
    """Calls such as logger.exception(...), logging.warning(...) or print(...)."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in ("logger", "logging"):
            yield node
        elif isinstance(func, ast.Name) and func.id == "print":
            yield node


@pytest.mark.parametrize("path", LOGIN_FILES)
def test_no_password_value_is_logged(path):
    for call in logging_calls(parse(path)):
        arguments = [*call.args, *(keyword.value for keyword in call.keywords)]
        mentioned = {name for argument in arguments for name in names_in(argument)}
        assert not any(("password" in name or "salt" in name) and " " not in name for name in mentioned), (
            f"{path}:{call.lineno} logs something password-related"
        )


def test_current_user_is_set_only_by_switch_user_and_log_out():
    setters = set()
    for function in ast.walk(parse("app.py")):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            targets = node.targets if isinstance(node, ast.Assign) else []
            targets += [node.target] if isinstance(node, (ast.AugAssign, ast.AnnAssign)) else []
            if any(isinstance(target, ast.Attribute) and target.attr == "current_user" for target in targets):
                setters.add(function.name)
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
                if node.slice.value == "current_user" and isinstance(node.ctx, ast.Store):
                    setters.add(function.name)
    assert setters == {"switch_user", "log_out"}
