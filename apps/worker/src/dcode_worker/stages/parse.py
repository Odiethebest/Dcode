"""Pipeline stage: discover and parse Python files with the stdlib AST."""

import ast
import logging
from pathlib import Path

from dcode_worker.context import PipelineContext
from dcode_worker.models import ParsedPythonFile

logger = logging.getLogger("dcode.worker.stages.parse")

SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


async def run(ctx: PipelineContext) -> PipelineContext:
    """Walk the cloned workdir and parse valid `.py` files.

    Syntax or decoding errors are recorded as warnings and skipped so a single
    bad file does not fail an otherwise useful repository index.
    """
    if ctx.workdir is None:
        raise RuntimeError("parse stage requires ctx.workdir from clone stage")

    root = Path(ctx.workdir).resolve()
    parsed_files: list[ParsedPythonFile] = []
    warnings: list[str] = []

    for path in _iter_python_files(root):
        relative_path = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            warning = f"skipped undecodable Python file {relative_path}: {exc}"
            warnings.append(warning)
            logger.warning(warning)
            continue

        try:
            tree = ast.parse(source, filename=relative_path)
        except SyntaxError as exc:
            warning = f"skipped unparsable Python file {relative_path}: {exc.msg}"
            warnings.append(warning)
            logger.warning(warning)
            continue

        parsed_files.append(
            ParsedPythonFile(
                file_path=relative_path,
                source=source,
                tree=tree,
                imports=_module_imports(tree),
            )
        )

    ctx.files = [parsed.file_path for parsed in parsed_files]
    ctx.parsed_files = parsed_files
    ctx.warnings.extend(warnings)
    return ctx


def _iter_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.relative_to(root).parts[:-1]):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def _module_imports(tree: ast.Module) -> list[str]:
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            imports.extend(_format_import(node))
    return _unique(imports)


def _format_import(node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [f"import {_format_alias(alias)}" for alias in node.names]

    module = "." * node.level + (node.module or "")
    return [f"from {module} import {_format_alias(alias)}" for alias in node.names]


def _format_alias(alias: ast.alias) -> str:
    if alias.asname is None:
        return alias.name
    return f"{alias.name} as {alias.asname}"


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
