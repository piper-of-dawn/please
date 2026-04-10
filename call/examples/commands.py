from call import call


@call
def sum(a: int, b: int) -> None:
    print(a + b)


@call
def greet(name: str, title: str = "friend") -> None:
    print(f"Hello, {title} {name}")


@call
def divide(a: float, b: float) -> None:
    print(a / b)
