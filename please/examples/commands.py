from please import please


@please
def sum(a: int, b: int) -> None:
    print(a + b)


@please
def greet(name: str, title: str = "friend") -> None:
    print(f"Hello, {title} {name}")


@please
def divide(a: float, b: float) -> None:
    print(a / b)
