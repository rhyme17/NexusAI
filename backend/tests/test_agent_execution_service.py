from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.models.agent import Agent
from backend.app.models.task import Task, TaskPriority
from backend.app.services import agent_execution as execution_module


class _DummyCompletions:
    def create(self, **_: object):
        class _Message:
            content = "provider summary"

        class _Choice:
            message = _Message()

        class _Usage:
            prompt_tokens = 11
            completion_tokens = 9
            total_tokens = 20

        class _Response:
            choices = [_Choice()]
            usage = _Usage()

        return _Response()


class _DummyChat:
    completions = _DummyCompletions()


class _DummyClient:
    chat = _DummyChat()


class _DummyOpenAIModule:
    class OpenAI:
        def __init__(self, **_: object) -> None:
            self.chat = _DummyChat()


class _EmptyChoicesCompletions:
    def create(self, **_: object):
        class _Response:
            choices = None

        return _Response()


class _EmptyChoicesOpenAIModule:
    class OpenAI:
        def __init__(self, **_: object) -> None:
            class _Chat:
                completions = _EmptyChoicesCompletions()

            self.chat = _Chat()


class _CapturingOpenAIModule:
    captured_init_kwargs: dict[str, object] = {}

    class OpenAI:
        def __init__(self, **kwargs: object) -> None:
            _CapturingOpenAIModule.captured_init_kwargs = kwargs
            self.chat = _DummyChat()


class _RecordingCompletions:
    captured_create_kwargs: dict[str, object] = {}

    def create(self, **kwargs: object):
        _RecordingCompletions.captured_create_kwargs = kwargs

        class _Response:
            choices = (
                {"message": {"content": [{"text": "provider"}, {"content": "summary"}] }},
            )
            usage = {"prompt_tokens": "7", "completion_tokens": 3, "total_tokens": "10"}

        return _Response()


class _NormalizedResponseOpenAIModule:
    captured_init_kwargs: dict[str, object] = {}

    class OpenAI:
        def __init__(self, **kwargs: object) -> None:
            _NormalizedResponseOpenAIModule.captured_init_kwargs = kwargs

            class _Chat:
                completions = _RecordingCompletions()

            self.chat = _Chat()


def test_agent_execution_service_uses_role_prompt_and_extracts_usage(monkeypatch) -> None:
    monkeypatch.setenv("MODELSCOPE_TOKEN", "dummy-token")
    monkeypatch.setenv("NEXUSAI_AGENT_EXECUTION_MODEL", "Qwen/test-model")
    monkeypatch.setattr(execution_module, "import_module", lambda _: _DummyOpenAIModule)

    service = execution_module.AgentExecutionService()
    task = Task(task_id="task_demo", objective="review demo output", priority=TaskPriority.MEDIUM)
    agent = Agent(agent_id="agent_reviewer", name="reviewer-agent", role="reviewer", skills=["review"])

    result = service.execute(task=task, agent=agent)

    assert result.result["summary"] == "provider summary"
    assert result.result["mode"] == "real"
    assert result.result["model"] == "Qwen/test-model"
    assert result.result["execution_metrics"]["usage"]["total_tokens"] == 20
    assert result.metrics is not None
    assert result.metrics["usage"]["prompt_tokens"] == 11


def test_role_instruction_template_contains_role_specific_guidance() -> None:
    service = execution_module.AgentExecutionService()
    agent = Agent(agent_id="agent_planner", name="planner-agent", role="planner", skills=["plan"])

    prompt = service._build_system_prompt(agent)

    assert "Planner Agent" in prompt
    assert "dependencies" in prompt


def test_role_instruction_template_supports_judge_role() -> None:
    service = execution_module.AgentExecutionService()
    agent = Agent(agent_id="agent_judge", name="judge-agent", role="judge", skills=["arbitration"])

    prompt = service._build_system_prompt(agent)

    assert "Judge Agent" in prompt
    assert "conflicts" in prompt


def test_agent_execution_service_rejects_unsupported_provider(monkeypatch) -> None:
    monkeypatch.setenv("MODELSCOPE_TOKEN", "dummy-token")
    service = execution_module.AgentExecutionService()
    task = Task(task_id="task_demo", objective="review demo output", priority=TaskPriority.MEDIUM)
    agent = Agent(agent_id="agent_reviewer", name="reviewer-agent", role="reviewer", skills=["review"])

    try:
        service.execute(task=task, agent=agent, provider="anthropic")
        assert False, "expected AgentExecutionError"
    except execution_module.AgentExecutionError as exc:
        assert exc.code == "E_EXECUTION_CONFIG"
        assert "Unsupported execution provider" in exc.message
        assert exc.metadata["category"] == "configuration"
        assert exc.metadata["retryable"] is False
        assert exc.details["provider"] == "anthropic"


def test_agent_execution_service_prefers_request_api_key_over_env(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_AGENT_EXECUTION_API_KEY", "env-token")
    monkeypatch.setattr(execution_module, "import_module", lambda _: _CapturingOpenAIModule)

    service = execution_module.AgentExecutionService()
    task = Task(task_id="task_demo", objective="execute with custom key", priority=TaskPriority.MEDIUM)
    agent = Agent(agent_id="agent_planner", name="planner-agent", role="planner", skills=["plan"])

    service.execute(task=task, agent=agent, api_key="request-token")

    assert _CapturingOpenAIModule.captured_init_kwargs.get("api_key") == "request-token"


def test_agent_execution_service_supports_modelscope_access_token_alias(monkeypatch) -> None:
    monkeypatch.delenv("NEXUSAI_AGENT_EXECUTION_API_KEY", raising=False)
    monkeypatch.delenv("MODELSCOPE_TOKEN", raising=False)
    monkeypatch.setenv("MODELSCOPE_ACCESS_TOKEN", "alias-token")
    monkeypatch.setattr(execution_module, "import_module", lambda _: _CapturingOpenAIModule)

    service = execution_module.AgentExecutionService()
    task = Task(task_id="task_demo", objective="execute with alias key", priority=TaskPriority.MEDIUM)
    agent = Agent(agent_id="agent_planner", name="planner-agent", role="planner", skills=["plan"])

    service.execute(task=task, agent=agent)

    assert _CapturingOpenAIModule.captured_init_kwargs.get("api_key") == "alias-token"


def test_agent_execution_service_defaults_to_deepseek_model_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("NEXUSAI_AGENT_EXECUTION_MODEL", raising=False)
    monkeypatch.setenv("MODELSCOPE_TOKEN", "dummy-token")
    monkeypatch.setattr(execution_module, "import_module", lambda _: _CapturingOpenAIModule)

    service = execution_module.AgentExecutionService()
    task = Task(task_id="task_demo", objective="check default model", priority=TaskPriority.MEDIUM)
    agent = Agent(agent_id="agent_planner", name="planner-agent", role="planner", skills=["plan"])

    service.execute(task=task, agent=agent)

    assert _CapturingOpenAIModule.captured_init_kwargs.get("api_key") == "dummy-token"
    assert service._resolve_model_name(None) == "deepseek-ai/DeepSeek-V3.2"


def test_agent_execution_service_trims_blank_overrides_and_parses_variant_response(monkeypatch) -> None:
    monkeypatch.setenv("MODELSCOPE_TOKEN", "dummy-token")
    monkeypatch.setenv("NEXUSAI_AGENT_EXECUTION_MODEL", "Qwen/trimmed-model")
    monkeypatch.setattr(execution_module, "import_module", lambda _: _NormalizedResponseOpenAIModule)

    service = execution_module.AgentExecutionService()
    task = Task(task_id="task_demo", objective="normalize execution inputs", priority=TaskPriority.MEDIUM)
    agent = Agent(agent_id="agent_planner", name="planner-agent", role="planner", skills=["plan"])

    result = service.execute(task=task, agent=agent, model="   ", system_instruction="   ")

    assert _NormalizedResponseOpenAIModule.captured_init_kwargs.get("api_key") == "dummy-token"
    assert _RecordingCompletions.captured_create_kwargs.get("model") == "Qwen/trimmed-model"
    assert _RecordingCompletions.captured_create_kwargs.get("messages")[0]["content"] == execution_module.get_role_instruction_template(
        agent.role
    )
    assert result.result["summary"] == "provider\nsummary"
    assert result.result["execution_metrics"]["usage"]["total_tokens"] == 10
    assert result.metrics is not None
    assert result.metrics["usage"]["prompt_tokens"] == 7


def test_agent_execution_service_wraps_client_init_type_error(monkeypatch) -> None:
    class _BrokenOpenAIModule:
        class OpenAI:
            def __init__(self, **_: object) -> None:
                raise TypeError("Client.__init__() got an unexpected keyword argument 'proxies'")

    monkeypatch.setenv("MODELSCOPE_TOKEN", "dummy-token")
    monkeypatch.setattr(execution_module, "import_module", lambda _: _BrokenOpenAIModule)

    service = execution_module.AgentExecutionService()
    task = Task(task_id="task_demo", objective="trigger init error", priority=TaskPriority.MEDIUM)
    agent = Agent(agent_id="agent_planner", name="planner-agent", role="planner", skills=["plan"])

    try:
        service.execute(task=task, agent=agent)
        assert False, "expected AgentExecutionError"
    except execution_module.AgentExecutionError as exc:
        assert exc.code == "E_EXECUTION_PROVIDER"
        assert "Provider client initialization failed" in exc.message
        assert exc.details.get("hint") == "Check dependency compatibility between openai and httpx."


def test_user_prompt_targets_final_deliverable_instead_of_process_summary() -> None:
    service = execution_module.AgentExecutionService()
    task = Task(
        task_id="task_report",
        objective="research blockchain security and output a report",
        priority=TaskPriority.HIGH,
        metadata={"output_format": "markdown"},
    )
    agent = Agent(agent_id="agent_analyst", name="analyst-agent", role="analyst", skills=["analysis"])

    prompt = service._build_user_prompt(task, agent)

    assert "final deliverable" in prompt
    assert "Output format: Markdown" in prompt
    assert "concise result summary" not in prompt


def test_agent_execution_service_handles_missing_choices_without_500(monkeypatch) -> None:
    monkeypatch.setenv("MODELSCOPE_TOKEN", "dummy-token")
    monkeypatch.setattr(execution_module, "import_module", lambda _: _EmptyChoicesOpenAIModule)

    service = execution_module.AgentExecutionService()
    task = Task(task_id="task_demo", objective="trigger malformed provider response", priority=TaskPriority.MEDIUM)
    agent = Agent(agent_id="agent_writer", name="writer-agent", role="writer", skills=["write"])

    try:
        service.execute(task=task, agent=agent)
        assert False, "expected AgentExecutionError"
    except execution_module.AgentExecutionError as exc:
        assert exc.code == "E_EXECUTION_EMPTY"
        assert "choices" in exc.message.lower()


