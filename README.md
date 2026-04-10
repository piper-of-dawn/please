# call

`call` is a small decorator-based Python CLI runner. You register normal Python functions with `@call`, and the framework exposes them as terminal commands.

## Design

User functions keep natural signatures:

```python
from call import call

@call
def sum(a: int, b: int) -> None:
    print(a + b)
```

The framework does not force `def cmd(context)`. Internally it still builds a dictionary-like `InvocationContext` with the parsed positional args, named args, bound values, warnings, and framework options like `--log`.

## Install

With `pipx`:

```bash
pipx install .
```

After that, the `call` command is available on your `PATH`.

## Project structure

```text
call/
  __init__.py
  cli.py
  core.py
  examples/
    commands.py
tests/
  test_commands.py
  test_commands_support.py
```

## How it works

- `call <COMMAND> <ARGS>` dispatches to a registered function.
- Positional and named styles are both supported for the same command.
- If a parameter has a type annotation, `call` tries to coerce the CLI value to that type.
- Unknown named args and extra positional args produce warnings on stderr.
- Missing required args produce a clear error and a non-zero exit code.
- `--log <file>` is handled by the framework and tees both stdout and stderr into the log file.

## Example commands

Built-in example commands live in `call/examples/commands.py`:

```bash
call sum 1 2
call sum -a 1 -b 2
call sum 1 2 --log log.txt
call greet Ada
call divide -a 6 -b 2
```

## Registering your own commands

The CLI auto-loads built-in examples, any extra modules listed in the `CALL_MODULES` environment variable, and any newline-delimited entries listed in `CALL_MODULES` files found in the current directory or its parents.

```python
# my_commands.py
from call import call

@call
def hello(name: str, title: str = "friend") -> None:
    print(f"Hello, {title} {name}")
```

Run it like this:

```bash
CALL_MODULES=my_commands call hello Ada
CALL_MODULES=my_commands call hello -name Ada -title Engineer
```

Or put entries in a `CALL_MODULES` file:

```text
my_commands
my_other_commands
./commands/custom.py
```

Each line can be either an importable module name or a relative Python file path. Relative paths are resolved from the directory containing that `CALL_MODULES` file. File-based entries are discovered from the current working directory upward, and they are appended after the `CALL_MODULES` environment variable.

## Errors and warnings

Examples:

```bash
$ call sum 1
error: Missing required argument for command 'sum': b.

$ call sum 1 2 3
warning: Unused positional arguments: '3'
3

$ call sum 1 2 -c 3
warning: Unknown named arguments: c='3'
3
```

## Tests

Run:

```bash
python -m unittest discover -s tests -v
```
