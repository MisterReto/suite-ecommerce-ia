"""Freeze the accepted pipeline against an immutable repository snapshot."""
import ast
import hashlib
import json
import subprocess
from pathlib import Path


def _selected_tree(source, selected):
    tree = ast.parse(source)
    nodes = tree.body if selected is None else [
        node for node in tree.body
        if getattr(node, "name", None) in selected or isinstance(node, ast.Assign)
        and any(getattr(target, "id", "") in selected for target in node.targets)
    ]
    if selected is not None:
        found = {getattr(node, "name", None) for node in nodes}
        found.update(
            getattr(target, "id", None)
            for node in nodes if isinstance(node, ast.Assign)
            for target in node.targets
        )
        assert set(selected) <= found, "A protected definition is missing"
    return ast.Module(body=nodes, type_ignores=[])


def _fingerprint(tree):
    # Both snapshots are parsed and serialized by this same interpreter.
    return hashlib.sha256(
        ast.dump(tree, include_attributes=False).encode()
    ).hexdigest()


def test_accepted_generation_pipeline_has_not_changed():
    root = Path(__file__).parent
    contract = json.loads(
        (root / "tests/fixtures/generation_contract.json").read_text(encoding="utf-8")
    )
    accepted = contract["accepted_commit"]
    assert len(accepted) == 40 and all(c in "0123456789abcdef" for c in accepted)
    for filename, selected in contract["protected"].items():
        snapshot = subprocess.run(
            ["git", "show", f"{accepted}:{filename}"],
            cwd=root, capture_output=True, text=True, encoding="utf-8",
        )
        assert snapshot.returncode == 0, (
            f"Accepted generation snapshot unavailable: {accepted}:{filename}. "
            "Fetch repository history before running the contract test."
        )
        baseline = _selected_tree(snapshot.stdout, selected)
        current = _selected_tree((root / filename).read_text(encoding="utf-8"), selected)
        assert _fingerprint(current) == _fingerprint(baseline), (
            f"Protected generation changed: {filename}"
        )


def test_freeze_detects_prompt_changes_and_collection_changes():
    original = ast.parse("prompt = 'Keep the original product'\n")
    changed = ast.parse("prompt = 'Replace the product'\n")
    assert _fingerprint(original) != _fingerprint(changed)
    assert _fingerprint(ast.parse("references = []")) != _fingerprint(
        ast.parse("references = {}")
    )


def test_freeze_rejects_missing_protected_definition():
    try:
        _selected_tree("def unrelated():\n    pass\n", ["generate"])
    except AssertionError:
        return
    raise AssertionError("Removing a protected function must invalidate the contract")
