"""Decorators for storage service handlers."""

from collections.abc import Callable
from functools import wraps
from typing import Concatenate, ParamSpec, Protocol, TypeVar


class HandlerInitializable(Protocol):
    def _initialize_handlers(self) -> None: ...


Self = TypeVar("Self", bound=HandlerInitializable)
Parameters = ParamSpec("Parameters")
Result = TypeVar("Result")


def ensure_handlers_initialized(
    func: Callable[Concatenate[Self, Parameters], Result],
) -> Callable[Concatenate[Self, Parameters], Result]:
    """
    Decorator to ensure handlers are initialized before method execution.

    This reduces repetition across FileStorageService methods that delegate
    to specialized handlers.

    Args:
        func: Method to wrap

    Returns:
        Wrapped method that initializes handlers first
    """

    @wraps(func)
    def wrapper(
        self: Self, *args: Parameters.args, **kwargs: Parameters.kwargs
    ) -> Result:
        self._initialize_handlers()
        return func(self, *args, **kwargs)

    return wrapper
