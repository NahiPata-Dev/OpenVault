import json
import os
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from uuid import UUID

from pydantic import ValidationError

from app.schemas import ResourceMatchResult


class AIProviderNotConfigured(Exception):
    pass


class AIProviderError(Exception):
    pass


def ai_provider_configured() -> bool:
    return bool(
        os.environ.get("AI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
    )


def complete_chat(messages: list[dict[str, str]]) -> str:
    api_key = (
        os.environ.get("AI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
    )
    if not api_key:
        raise AIProviderNotConfigured

    openrouter_configured = bool(os.environ.get("OPENROUTER_API_KEY"))
    default_base_url = (
        "https://openrouter.ai/api/v1"
        if openrouter_configured
        else "https://api.openai.com/v1"
    )
    base_url = os.environ.get("AI_BASE_URL", default_base_url).rstrip("/")
    parsed_base_url = urlparse(base_url)
    local_http_host = parsed_base_url.hostname in {"localhost", "127.0.0.1", "::1"}
    if not parsed_base_url.netloc or (
        parsed_base_url.scheme != "https"
        and not (parsed_base_url.scheme == "http" and local_http_host)
    ):
        raise AIProviderError
    default_model = "openai/gpt-4o-mini" if openrouter_configured else "gpt-4o-mini"
    payload = {
        "model": os.environ.get(
            "AI_MODEL", os.environ.get("OPENROUTER_MODEL", default_model)
        ),
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 900,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if openrouter_configured:
        site_url = os.environ.get("OPENROUTER_SITE_URL")
        app_name = os.environ.get("OPENROUTER_APP_NAME")
        if site_url:
            headers["HTTP-Referer"] = site_url
        if app_name:
            headers["X-Title"] = app_name
    request = Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
        raise AIProviderError from error

    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise AIProviderError from error
    if not isinstance(content, str) or not content.strip():
        raise AIProviderError
    return content.strip()


class ResourceMatchProvider(Protocol):
    def match(self, goal: str, candidates: list[dict]) -> dict: ...


def validate_provider_result(
    payload: dict,
    allowed_resource_ids: set[str],
    deterministic_fallback: ResourceMatchResult,
) -> ResourceMatchResult:
    try:
        result = ResourceMatchResult.model_validate(payload)
        candidate_ids = [str(candidate.resource_id) for candidate in result.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Duplicate candidate IDs")
        if any(resource_id not in allowed_resource_ids for resource_id in candidate_ids):
            return deterministic_fallback.model_copy(
                update={
                    "source": "deterministic_fallback",
                    "disclosure": "Untrusted matching output was discarded; deterministic suggestions are shown.",
                }
            )
        return result
    except (ValidationError, ValueError):
        return deterministic_fallback.model_copy(
            update={
                "source": "deterministic_fallback",
                "disclosure": "Untrusted matching output was discarded; deterministic suggestions are shown.",
            }
        )


def validate_resource_id(value: str) -> str:
    return str(UUID(value))
