from __future__ import annotations

from collections.abc import Iterable, Iterator, MutableMapping
from dataclasses import dataclass, field
import inspect
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints


class JustError(Exception):
    """Base error for framework-level failures."""


class CommandRegistrationError(JustError):
    """Raised when a function signature cannot be supported."""


class CommandNotFoundError(JustError):
    """Raised when the requested command is not registered."""


class ArgumentParseError(JustError):
    """Raised when CLI tokens cannot be parsed."""


class MissingArgumentsError(JustError):
    """Raised when a command is missing required arguments."""


class TypeCoercionError(JustError):
    """Raised when a CLI value cannot be coerced to a parameter type."""


class InvocationContext(MutableMapping[str, Any]):
    """Dictionary-like command metadata available to the framework layer."""

    def __init__(
        self,
        *,
        command_name: str,
        raw_argv: list[str],
        positional_tokens: list[str],
        named_tokens: dict[str, str],
        log_file: str | None,
    ) -> None:
        self.command_name = command_name
        self.raw_argv = list(raw_argv)
        self.log_file = log_file
        self._data: dict[str, Any] = {
            "command": command_name,
            "argv": list(raw_argv),
            "positional": list(positional_tokens),
            "named": dict(named_tokens),
            "log_file": log_file,
            "bound": {},
            "warnings": [],
        }

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


@dataclass(slots=True)
class ParsedArgs:
    positional: list[str]
    named: dict[str, str]
    log_file: str | None = None


@dataclass(slots=True)
class Command:
    name: str
    func: Any
    signature: inspect.Signature
    parameters: list[inspect.Parameter] = field(default_factory=list)


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, func: Any) -> Any:
        signature = inspect.signature(func)
        resolved_hints = get_type_hints(func)
        parameters = [
            parameter.replace(annotation=resolved_hints.get(parameter.name, parameter.annotation))
            for parameter in signature.parameters.values()
        ]
        unsupported = [
            param.name
            for param in parameters
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        if unsupported:
            joined = ", ".join(unsupported)
            raise CommandRegistrationError(
                f"Command '{func.__name__}' uses unsupported parameter kinds: {joined}."
            )
        command = Command(
            name=func.__name__.replace("_", "-"),
            func=func,
            signature=signature,
            parameters=parameters,
        )
        self._commands[command.name] = command
        return func

    def get(self, name: str) -> Command:
        try:
            return self._commands[name]
        except KeyError as exc:
            known = ", ".join(sorted(self._commands)) or "none"
            raise CommandNotFoundError(
                f"Unknown command '{name}'. Available commands: {known}."
            ) from exc

    def items(self) -> Iterable[tuple[str, Command]]:
        return self._commands.items()


registry = CommandRegistry()


def please(func: Any) -> Any:
    return registry.register(func)


def parse_argv(argv: list[str]) -> ParsedArgs:
    positional: list[str] = []
    named: dict[str, str] = {}
    log_file: str | None = None
    index = 0
    positional_only = False

    while index < len(argv):
        token = argv[index]

        if positional_only:
            positional.append(token)
            index += 1
            continue

        if token == "--":
            positional_only = True
            index += 1
            continue

        if token == "--log":
            if index + 1 >= len(argv):
                raise ArgumentParseError("Framework option '--log' requires a file path.")
            log_file = argv[index + 1]
            index += 2
            continue

        if token.startswith("--") and len(token) > 2:
            name, value, consumed = _parse_named_token(token, argv, index)
            named[name] = value
            index += consumed
            continue

        if token.startswith("-") and len(token) > 1:
            name, value, consumed = _parse_named_token(token, argv, index)
            named[name] = value
            index += consumed
            continue

        positional.append(token)
        index += 1

    return ParsedArgs(positional=positional, named=named, log_file=log_file)


def build_context(command_name: str, raw_argv: list[str], parsed: ParsedArgs) -> InvocationContext:
    return InvocationContext(
        command_name=command_name,
        raw_argv=raw_argv,
        positional_tokens=parsed.positional,
        named_tokens=parsed.named,
        log_file=parsed.log_file,
    )


def bind_command(command: Command, parsed: ParsedArgs, context: InvocationContext) -> tuple[list[Any], dict[str, Any]]:
    remaining_positional = list(parsed.positional)
    provided_named = dict(parsed.named)
    bound_values: dict[str, Any] = {}
    missing: list[str] = []

    for parameter in command.parameters:
        if parameter.name in provided_named:
            raw_value = provided_named.pop(parameter.name)
            bound_values[parameter.name] = coerce_value(raw_value, parameter)
            continue

        if parameter.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ) and remaining_positional:
            raw_value = remaining_positional.pop(0)
            bound_values[parameter.name] = coerce_value(raw_value, parameter)
            continue

        if parameter.default is not inspect._empty:
            continue

        missing.append(parameter.name)

    warnings: list[str] = []
    if remaining_positional:
        warnings.append(
            "Unused positional arguments: " + ", ".join(repr(value) for value in remaining_positional)
        )
    if provided_named:
        warnings.append(
            "Unknown named arguments: "
            + ", ".join(f"{name}={value!r}" for name, value in sorted(provided_named.items()))
        )

    context["bound"] = dict(bound_values)
    context["warnings"] = list(warnings)
    context["unused_positional"] = list(remaining_positional)
    context["unknown_named"] = dict(provided_named)

    if missing:
        plural = "argument" if len(missing) == 1 else "arguments"
        raise MissingArgumentsError(
            f"Missing required {plural} for command '{command.name}': {', '.join(missing)}."
        )

    args: list[Any] = []
    kwargs: dict[str, Any] = {}
    for parameter in command.parameters:
        if parameter.name not in bound_values:
            continue
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY:
            kwargs[parameter.name] = bound_values[parameter.name]
        else:
            args.append(bound_values[parameter.name])

    return args, kwargs


def coerce_value(raw_value: str, parameter: inspect.Parameter) -> Any:
    annotation = parameter.annotation
    if annotation is inspect._empty:
        return raw_value

    origin = get_origin(annotation)
    if origin is None:
        return _coerce_to_type(raw_value, annotation, parameter.name)

    if origin is list:
        item_type = get_args(annotation)[0] if get_args(annotation) else str
        return [_coerce_to_type(part, item_type, parameter.name) for part in raw_value.split(",")]

    if origin is tuple:
        item_types = get_args(annotation)
        values = raw_value.split(",")
        if item_types and len(item_types) == len(values):
            return tuple(
                _coerce_to_type(value, item_type, parameter.name)
                for value, item_type in zip(values, item_types, strict=True)
            )
        return tuple(values)

    if origin is Any:
        return raw_value

    if origin is not None and type(None) in get_args(annotation):
        non_none = [item for item in get_args(annotation) if item is not type(None)]
        if raw_value.lower() in {"none", "null"}:
            return None
        if len(non_none) == 1:
            return _coerce_to_type(raw_value, non_none[0], parameter.name)

    return raw_value


def _coerce_to_type(raw_value: str, annotation: Any, parameter_name: str) -> Any:
    try:
        if annotation is bool:
            normalized = raw_value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            raise ValueError("expected a boolean value")
        if annotation in {str, int, float, Path}:
            return annotation(raw_value)
        return annotation(raw_value)
    except Exception as exc:  # noqa: BLE001
        raise TypeCoercionError(
            f"Could not coerce argument '{parameter_name}' value {raw_value!r} to {type_name(annotation)}."
        ) from exc


def type_name(annotation: Any) -> str:
    return getattr(annotation, "__name__", str(annotation))


def _parse_named_token(token: str, argv: list[str], index: int) -> tuple[str, str, int]:
    stripped = token.lstrip("-")
    if "=" in stripped:
        name, value = stripped.split("=", 1)
        if not name:
            raise ArgumentParseError(f"Invalid named argument syntax: {token!r}.")
        return name.replace("-", "_"), value, 1

    if index + 1 >= len(argv):
        raise ArgumentParseError(f"Named argument '{token}' requires a value.")

    value = argv[index + 1]
    return stripped.replace("-", "_"), value, 2
