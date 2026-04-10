from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from importlib import import_module
from time import perf_counter
from typing import Any

from ..core.config import (
    get_agent_execution_api_key,
    get_agent_execution_base_url,
    get_agent_execution_fallback,
    get_agent_execution_model,
    get_agent_execution_timeout_seconds,
    get_role_instruction_template,
)
from ..models.agent import Agent
from ..models.task import Task


EXECUTION_ERROR_METADATA: dict[str, dict[str, Any]] = {
    "E_EXECUTION_CONFIG": {
        "category": "configuration",
        "retryable": False,
        "user_message": "执行配置不可用，请检查模型提供方、模型配置或 API Key。",
    },
    "E_EXECUTION_PROVIDER": {
        "category": "provider",
        "retryable": True,
        "user_message": "模型服务调用失败，可稍后重试，或使用模拟回退继续当前流程。",
    },
    "E_EXECUTION_EMPTY": {
        "category": "empty_result",
        "retryable": True,
        "user_message": "模型返回了空结果，本次执行没有产生可用内容。",
    },
}


def get_execution_error_metadata(code: str) -> dict[str, Any]:
    return dict(
        EXECUTION_ERROR_METADATA.get(
            code,
            {
                "category": "unknown",
                "retryable": False,
                "user_message": "执行失败，请检查详细错误信息。",
            },
        )
    )


class AgentExecutionError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    @property
    def metadata(self) -> dict[str, Any]:
        return get_execution_error_metadata(self.code)

    def to_payload(self, **context: Any) -> dict[str, Any]:
        payload = {
            "error_code": self.code,
            "error_message": self.message,
            "error_category": self.metadata["category"],
            "retryable": self.metadata["retryable"],
            "user_message": self.metadata["user_message"],
        }
        if self.details:
            payload["details"] = dict(self.details)
        for key, value in context.items():
            if value is not None:
                payload[key] = value
        return payload


@dataclass
class AgentExecutionResult:
    result: dict[str, Any]
    confidence: float = 0.75
    metrics: dict[str, Any] | None = None


class AgentExecutionService:
    """OpenAI-compatible real execution adapter for role-based agents."""

    def execute(
        self,
        *,
        task: Task,
        agent: Agent,
        provider: str = "openai_compatible",
        api_key: str | None = None,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> AgentExecutionResult:
        if provider != "openai_compatible":
            raise AgentExecutionError(
                code="E_EXECUTION_CONFIG",
                message=f"Unsupported execution provider: {provider}",
                details={"provider": provider, "supported_providers": ["openai_compatible"]},
            )

        resolved_api_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else get_agent_execution_api_key()
        if not resolved_api_key:
            raise AgentExecutionError(
                code="E_EXECUTION_CONFIG",
                message="Missing API key. Set NEXUSAI_AGENT_EXECUTION_API_KEY or MODELSCOPE_TOKEN.",
                details={"provider": provider, "base_url": get_agent_execution_base_url()},
            )

        provider_model = self._resolve_model_name(model)
        resolved_system_instruction = self._resolve_system_instruction(system_instruction, agent)
        messages = [
            {
                "role": "system",
                "content": resolved_system_instruction,
            },
            {
                "role": "user",
                "content": self._build_user_prompt(task, agent),
            },
        ]

        try:
            OpenAI = import_module("openai").OpenAI
        except Exception as exc:
            raise AgentExecutionError(
                code="E_EXECUTION_PROVIDER",
                message="OpenAI SDK is not available. Install dependency 'openai'.",
                details={"provider": provider, "sdk": "openai"},
            ) from exc

        response, elapsed_ms = self._call_openai_compatible(
            openai_cls=OpenAI,
            api_key=resolved_api_key,
            model=provider_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = self._extract_text_content(response, model=provider_model)
        usage = self._extract_usage(response)

        content = content.strip()
        if not content:
            raise AgentExecutionError(
                code="E_EXECUTION_EMPTY",
                message="Provider returned empty content.",
                details={"provider": provider, "model": provider_model},
            )

        return AgentExecutionResult(
            result={
                "summary": content,
                "mode": "real",
                "provider": provider,
                "model": provider_model,
                "agent_id": agent.agent_id,
                "agent_role": agent.role,
                "execution_metrics": {
                    "latency_ms": elapsed_ms,
                    "usage": usage,
                    "fallback_policy": get_agent_execution_fallback(),
                },
            },
            confidence=0.82,
            metrics={"latency_ms": elapsed_ms, "usage": usage},
        )

    def _call_openai_compatible(
        self,
        *,
        openai_cls: Any,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> tuple[Any, int]:
        try:
            client = openai_cls(
                base_url=get_agent_execution_base_url(),
                api_key=api_key,
                timeout=get_agent_execution_timeout_seconds(),
            )
        except Exception as exc:
            details = {
                "provider": "openai_compatible",
                "model": model,
                "base_url": get_agent_execution_base_url(),
            }
            # Common local failure: openai/httpx version mismatch (e.g. unexpected proxies kwarg).
            if isinstance(exc, TypeError) and "proxies" in str(exc):
                details["hint"] = "Check dependency compatibility between openai and httpx."
            raise AgentExecutionError(
                code="E_EXECUTION_PROVIDER",
                message=f"Provider client initialization failed: {exc}",
                details=details,
            ) from exc

        started = perf_counter()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=False,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise AgentExecutionError(
                code="E_EXECUTION_PROVIDER",
                message=f"Provider call failed: {exc}",
                details={"provider": "openai_compatible", "model": model, "base_url": get_agent_execution_base_url()},
            ) from exc
        return response, int((perf_counter() - started) * 1000)

    def _extract_text_content(self, response: Any, *, model: str) -> str:
        """Extract text from SDK response safely across minor payload shape differences."""
        choices = getattr(response, "choices", None)
        if isinstance(choices, Mapping):
            choices = list(choices.values())
        elif isinstance(choices, Sequence) and not isinstance(choices, (str, bytes, bytearray)):
            choices = list(choices)
        else:
            choices = None

        if not choices:
            raise AgentExecutionError(
                code="E_EXECUTION_EMPTY",
                message="Provider response did not include choices.",
                details={"provider": "openai_compatible", "model": model},
            )

        for choice in choices:
            content = self._extract_choice_content(choice)
            if isinstance(content, str):
                stripped = content.strip()
                if stripped:
                    return content
            elif isinstance(content, Sequence) and not isinstance(content, (str, bytes, bytearray)):
                parts: list[str] = []
                for item in content:
                    text = self._extract_content_text(item)
                    if text:
                        parts.append(text)
                joined = "\n".join(part for part in parts if part).strip()
                if joined:
                    return joined

        return ""

    def _extract_choice_content(self, choice: Any) -> Any:
        message = getattr(choice, "message", None)
        if message is None and isinstance(choice, Mapping):
            message = choice.get("message")

        if message is None:
            if isinstance(choice, Mapping) and "content" in choice:
                return choice.get("content")
            return getattr(choice, "content", None) if hasattr(choice, "content") else None
        return getattr(message, "content", None) if not isinstance(message, Mapping) else message.get("content")

    def _extract_content_text(self, item: Any) -> str | None:
        if isinstance(item, str):
            return item
        if isinstance(item, Mapping):
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                return text
            content = item.get("content")
            if isinstance(content, str) and content.strip():
                return content
        text = getattr(item, "text", None)
        if isinstance(text, str) and text.strip():
            return text
        content = getattr(item, "content", None)
        if isinstance(content, str) and content.strip():
            return content
        return None

    def _build_system_prompt(self, agent: Agent) -> str:
        return get_role_instruction_template(agent.role)

    def _build_user_prompt(self, task: Task, agent: Agent) -> str:
        requested_format = self._normalize_requested_output_format(task.metadata.get("output_format") if task.metadata else None)
        output_hint = "Markdown" if requested_format == "markdown" else "plain text"

        return (
            f"Task ID: {task.task_id}\n"
            f"Role: {agent.role}\n"
            f"Objective: {task.objective}\n"
            f"Priority: {task.priority.value}\n"
            f"Metadata: {task.metadata}\n\n"
            "Produce the final deliverable for the user objective, not a process recap.\n"
            f"Output format: {output_hint}.\n"
            "Requirements:\n"
            "1) Keep the output tightly aligned with the objective and include concrete findings.\n"
            "2) If the objective requests a report, return the full report body with clear sections.\n"
            "3) Do not include workflow status, task routing diagnostics, or internal orchestration notes unless explicitly requested.\n"
            "4) When evidence is uncertain, mark assumptions clearly.\n"
        )

    def _extract_usage(self, response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        if isinstance(usage, Mapping):
            source: Mapping[str, Any] = usage
            return {
                "prompt_tokens": self._coerce_int(source.get("prompt_tokens")),
                "completion_tokens": self._coerce_int(source.get("completion_tokens")),
                "total_tokens": self._coerce_int(source.get("total_tokens")),
            }
        return {
            "prompt_tokens": self._coerce_int(getattr(usage, "prompt_tokens", 0)),
            "completion_tokens": self._coerce_int(getattr(usage, "completion_tokens", 0)),
            "total_tokens": self._coerce_int(getattr(usage, "total_tokens", 0)),
        }

    def _resolve_model_name(self, model: str | None) -> str:
        if isinstance(model, str):
            stripped = model.strip()
            if stripped:
                return stripped
        return get_agent_execution_model()

    def _resolve_system_instruction(self, system_instruction: str | None, agent: Agent) -> str:
        if isinstance(system_instruction, str):
            stripped = system_instruction.strip()
            if stripped:
                return stripped
        return self._build_system_prompt(agent)

    def _normalize_requested_output_format(self, raw_format: Any) -> str:
        if not isinstance(raw_format, str):
            return "markdown"

        normalized = raw_format.strip().lower()
        if not normalized:
            return "markdown"
        if "markdown" in normalized or normalized in {"md"}:
            return "markdown"
        if normalized in {"text", "txt", "plaintext", "plain_text", "plain text"} or "text" in normalized:
            return "text"
        return "markdown"

    @staticmethod
    def _coerce_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0


_execution_service = AgentExecutionService()


def get_agent_execution_service() -> AgentExecutionService:
    return _execution_service

