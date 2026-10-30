from dataclasses import dataclass
from typing import Any


@dataclass
class APIError(Exception):
    code: str
    message: str
    status_code: int
    details: list[dict[str, Any]] | None = None


def raise_api_error(
    code: str,
    message: str,
    status_code: int,
    details: list[dict[str, Any]] | None = None,
) -> None:
    raise APIError(code, message, status_code, details or [])
