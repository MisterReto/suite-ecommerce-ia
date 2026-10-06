"""User-requested freeze of the creative pipeline accepted before platform migration."""
import ast
import hashlib
import json
from pathlib import Path


def _stable_ast_dump(node):
    """Use the recorded compact representation across supported Python versions.

    Python 3.13 changed ast.dump's default handling of empty list fields.
    Empty fields added by newer parsers (for example type_params) do not
    represent a change to the accepted generation code.
    """
    if isinstance(node, ast.AST):
        fields = []
        for name, value in ast.iter_fields(node):
            if value is None and getattr(type(node), name, ...) is None:
                continue
            if isinstance(value, list) and not value:
                continue
            fields.append(f"{name}={_stable_ast_dump(value)}")
        return f"{type(node).__name__}({', '.join(fields)})"
    if isinstance(node, list):
        return f"[{', '.join(_stable_ast_dump(item) for item in node)}]"
    return repr(node)


def _fingerprint(node):
    return hashlib.sha256(_stable_ast_dump(node).encode()).hexdigest()


def test_accepted_generation_pipeline_has_not_changed():
    root = Path(__file__).parent
    contract = json.loads(
        (root / "tests/fixtures/generation_contract.json").read_text(encoding="utf-8")
    )
    for filename, selected in contract["protected"].items():
        tree = ast.parse((root / filename).read_text(encoding="utf-8"))
        nodes = tree.body if selected is None else [
            node for node in tree.body
            if getattr(node, "name", None) in selected or isinstance(node, ast.Assign)
            and any(getattr(target, "id", "") in selected for target in node.targets)
        ]
        digest = _fingerprint(ast.Module(body=nodes, type_ignores=[]))
        assert digest == contract["sha256"][filename], (
            f"Protected generation changed: {filename}"
        )


def test_freeze_ignores_empty_parser_fields_added_between_python_versions():
    tree = ast.parse("def generate(prompt):\n    return prompt\n")
    function = tree.body[0]
    original = _fingerprint(tree)
    if "type_params" not in function._fields:
        function._fields = (*function._fields, "type_params")
    function.type_params = []
    assert _fingerprint(tree) == original


def test_freeze_detects_prompt_changes_and_collection_changes():
    original = ast.parse("prompt = 'Keep the original product'\n")
    changed = ast.parse("prompt = 'Replace the product'\n")
    assert _fingerprint(original) != _fingerprint(changed)
    assert _fingerprint(ast.parse("references = []")) != _fingerprint(
        ast.parse("references = {}")
    )
