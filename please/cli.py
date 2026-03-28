from __future__ import annotations

import contextlib
import importlib
import importlib.util
import io
import os
import sys
from pathlib import Path

from .core import (
    JustError,
    bind_command,
    build_context,
    parse_argv,
    registry,
)


DEFAULT_MODULES = ("please.examples.commands",)
MODULES_FILE = "PLEASE_MODULES"


class Tee(io.TextIOBase):
    def __init__(self, *streams: io.TextIOBase) -> None:
        self._streams = streams

    def write(self, data: str) -> int:
        for stream in self._streams:
            stream.write(data)
            stream.flush()
        return len(data)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    load_modules()

    if not argv:
        _print_usage()
        return 1

    command_name, *command_argv = argv
    try:
        command = registry.get(command_name)
        parsed = parse_argv(command_argv)
        context = build_context(command_name, command_argv, parsed)
        args, kwargs = bind_command(command, parsed, context)
    except JustError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    with maybe_log(parsed.log_file):
        for warning in context["warnings"]:
            print(f"warning: {warning}", file=sys.stderr)
        try:
            command.func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            print(f"error: command '{command_name}' failed: {exc}", file=sys.stderr)
            return 1
    return 0


def load_modules() -> None:
    module_refs = list(DEFAULT_MODULES)
    module_refs.extend(_modules_from_env_var(os.environ.get("PLEASE_MODULES", "")))
    module_refs.extend(_modules_from_files(Path.cwd()))

    seen = set()
    unique_module_refs = []
    for module_ref in module_refs:
        if module_ref in seen:
            continue
        seen.add(module_ref)
        unique_module_refs.append(module_ref)

    for module_ref in unique_module_refs:
        _import_module_ref(module_ref)


def _modules_from_env_var(value: str) -> list[str]:
    if not value.strip():
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _modules_from_files(start_dir: Path) -> list[str]:
    modules: list[str] = []
    for directory in (start_dir, *start_dir.parents):
        path = directory / MODULES_FILE
        if not path.is_file():
            continue
        modules.extend(_modules_from_file(path))
    return modules


def _modules_from_file(path: Path) -> list[str]:
    module_refs: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry:
            continue
        if _looks_like_path(entry):
            module_refs.append(str((path.parent / entry).resolve()))
            continue
        module_refs.append(entry)
    return module_refs


def _looks_like_path(value: str) -> bool:
    return "/" in value or value.endswith(".py") or value.startswith(".")


def _import_module_ref(module_ref: str) -> None:
    if module_ref.endswith(".py") or Path(module_ref).is_file():
        _import_module_from_path(Path(module_ref))
        return
    importlib.import_module(module_ref)


def _import_module_from_path(path: Path) -> None:
    resolved = path.resolve()
    module_name = f"please_dynamic_{abs(hash(str(resolved)))}"
    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from path: {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)


@contextlib.contextmanager
def maybe_log(log_file: str | None):
    if not log_file:
        yield
        return

    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        stdout = Tee(sys.stdout, handle)
        stderr = Tee(sys.stderr, handle)
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            yield


def _print_usage() -> None:
    available = ", ".join(name for name, _ in sorted(registry.items())) or "none"
    print("Usage: please <COMMAND> <ARGS> [--log <file>]", file=sys.stderr)
    print(f"Available commands: {available}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
