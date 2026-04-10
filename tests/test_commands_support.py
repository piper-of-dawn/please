from __future__ import annotations

import sys

from call import call


@call
def add(a: int, b: int) -> None:
    print(a + b)


@call
def emit(message: str) -> None:
    print(f"OUT: {message}")
    print(f"ERR: {message}", file=sys.stderr)
