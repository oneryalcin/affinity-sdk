from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ReqTestRef:
    req_id: str
    nodeid: str


def _is_pytest_mark_req(func: ast.expr) -> bool:
    # Matches: pytest.mark.req
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr != "req":
        return False
    mark = func.value
    if not isinstance(mark, ast.Attribute):
        return False
    if mark.attr != "mark":
        return False
    root = mark.value
    return isinstance(root, ast.Name) and root.id == "pytest"


def _req_ids_from_decorators(decorators: Sequence[ast.expr]) -> list[str]:
    req_ids: list[str] = []
    for dec in decorators:
        if not isinstance(dec, ast.Call):
            continue
        if not _is_pytest_mark_req(dec.func):
            continue
        if not dec.args:
            continue
        first = dec.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            req_ids.append(first.value)
    return req_ids


def _collect_req_test_refs(repo_root: Path) -> list[ReqTestRef]:
    refs: list[ReqTestRef] = []
    tests_dir = repo_root / "tests"
    for path in sorted(tests_dir.rglob("test_*.py")):
        rel = path.relative_to(repo_root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_req_ids = _req_ids_from_decorators(node.decorator_list)
                for child in node.body:
                    if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if not child.name.startswith("test"):
                        continue
                    func_req_ids = _req_ids_from_decorators(child.decorator_list)
                    req_ids = class_req_ids + func_req_ids
                    nodeid = f"{rel}::{node.name}::{child.name}"
                    for req_id in req_ids:
                        refs.append(ReqTestRef(req_id=req_id, nodeid=nodeid))

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test"
            ):
                func_req_ids = _req_ids_from_decorators(node.decorator_list)
                nodeid = f"{rel}::{node.name}"
                for req_id in func_req_ids:
                    refs.append(ReqTestRef(req_id=req_id, nodeid=nodeid))

    return refs


def _group_by_req(refs: Sequence[ReqTestRef]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for ref in refs:
        grouped.setdefault(ref.req_id, []).append(ref.nodeid)
    for req_id in list(grouped):
        grouped[req_id] = sorted(set(grouped[req_id]))
    return dict(sorted(grouped.items()))


def generate_markdown(
    *,
    spec_path: str,
    mapping: Mapping[str, Sequence[str]],
) -> str:
    lines: list[str] = []
    lines.append("# Requirements → Tests Mapping (Traceability)")
    lines.append("")
    lines.append(
        f"**Spec:** `{spec_path}`    \n**Note:** This file is auto-generated. Do not edit by hand."
    )
    lines.append("")
    lines.append("## How to read this")
    lines.append("")
    lines.append("- Each entry maps a requirement ID to pytest nodeids.")
    lines.append("- Tests are tagged with `@pytest.mark.req('<REQ-ID>')`.")
    lines.append("")

    for req_id, nodeids in mapping.items():
        lines.append(f"## {req_id}")
        lines.append("")
        if not nodeids:
            lines.append("- (no tests found)")
        else:
            for nodeid in nodeids:
                lines.append(f"- `{nodeid}`")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_mapping() -> dict[str, list[str]]:
    repo_root = Path(__file__).resolve().parents[1]
    return _group_by_req(_collect_req_test_refs(repo_root))


def write_mapping(*, output_path: str, spec_path: str) -> None:
    mapping = build_mapping()
    content = generate_markdown(spec_path=spec_path, mapping=mapping)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    _ = argv
    repo_root = Path(__file__).resolve().parents[1]
    output_path = repo_root / "docs" / "internal" / "requirements_to_tests_mapping.md"
    spec_path = "docs/internal/requirements_specification.md"
    write_mapping(output_path=str(output_path), spec_path=spec_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
