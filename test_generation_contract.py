"""User-requested freeze of the creative pipeline accepted before platform migration."""
import ast
import hashlib
import json
from pathlib import Path


def test_accepted_generation_pipeline_has_not_changed():
    root = Path(__file__).parent
    contract = json.loads((root / "tests/fixtures/generation_contract.json").read_text())
    for filename, selected in contract["protected"].items():
        tree = ast.parse((root / filename).read_text())
        nodes = tree.body if selected is None else [node for node in tree.body
            if getattr(node, "name", None) in selected or isinstance(node, ast.Assign)
            and any(getattr(target, "id", "") in selected for target in node.targets)]
        digest = hashlib.sha256(ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False).encode()).hexdigest()
        assert digest == contract["sha256"][filename], f"Protected generation changed: {filename}"
