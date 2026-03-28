from __future__ import annotations

import sys

from please import please


@please
def add(a: int, b: int) -> None:
    print(a + b)


@please
def emit(message: str) -> None:
    print(f"OUT: {message}")
    print(f"ERR: {message}", file=sys.stderr)
