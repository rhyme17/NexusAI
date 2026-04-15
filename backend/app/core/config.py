from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

SUPPORTED_CONSENSUS_STRATEGIES = {"highest_confidence", "majority_vote"}
FALLBACK_CONSENSUS_STRATEGY = "highest_confidence"
DEFAULT_CONSENSUS_ENV = "NEXUSAI_CONSENSUS_STRATEGY_DEFAULT"
EVENT_HISTORY_LIMIT_ENV = "NEXUSAI_EVENT_HISTORY_MAX"
DEFAULT_EVENT_HISTORY_LIMIT = 2000
MAX_RETRIES_ENV = "NEXUSAI_MAX_RETRIES_DEFAULT"
DEFAULT_MAX_RETRIES = 2
JSON_PERSISTENCE_ENABLED_ENV = "NEXUSAI_JSON_PERSISTENCE_ENABLED"
STORAGE_BACKEND_ENV = "NEXUSAI_STORAGE_BACKEND"
SQLITE_PATH_ENV = "NEXUSAI_SQLITE_PATH"
DATA_DIR_ENV = "NEXUSAI_DATA_DIR"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SEED_ENABLED_ENV = "NEXUSAI_SEED_ENABLED"
SEED_APPLY_IF_EMPTY_ENV = "NEXUSAI_SEED_APPLY_IF_EMPTY"
SEED_FILE_ENV = "NEXUSAI_SEED_FILE"
DEBUG_API_ENABLED_ENV = "NEXUSAI_DEBUG_API_ENABLED"
API_AUTH_ENABLED_ENV = "NEXUSAI_API_AUTH_ENABLED"
API_AUTH_KEYS_ENV = "NEXUSAI_API_KEYS"
API_AUTH_KEY_ROLES_ENV = "NEXUSAI_API_KEY_ROLES"
API_AUTH_DEFAULT_ROLE_ENV = "NEXUSAI_API_AUTH_DEFAULT_ROLE"
API_AUTH_EXEMPT_PATHS_ENV = "NEXUSAI_API_AUTH_EXEMPT_PATHS"
ENV_FILE_ENV = "NEXUSAI_ENV_FILE"
STARTUP_CLEAR_ENABLED_ENV = "NEXUSAI_CLEAR_ON_STARTUP"
STARTUP_CLEAR_EVENTS_ONLY_ENV = "NEXUSAI_CLEAR_EVENTS_ONLY_ON_STARTUP"
STARTUP_CLEAR_RESTORE_SEED_ENV = "NEXUSAI_CLEAR_RESTORE_SEED_ON_STARTUP"
POSTGRES_DSN_ENV = "NEXUSAI_POSTGRES_DSN"
STORAGE_FALLBACK_ON_ERROR_ENV = "NEXUSAI_STORAGE_FALLBACK_ON_ERROR"
STORAGE_FALLBACK_BACKEND_ENV = "NEXUSAI_STORAGE_FALLBACK_BACKEND"
READ_ONLY_MODE_ENV = "NEXUSAI_READ_ONLY_MODE"
AGENT_EXECUTION_BASE_URL_ENV = "NEXUSAI_AGENT_EXECUTION_BASE_URL"
AGENT_EXECUTION_MODEL_ENV = "NEXUSAI_AGENT_EXECUTION_MODEL"
AGENT_EXECUTION_API_KEY_ENV = "NEXUSAI_AGENT_EXECUTION_API_KEY"
MODELSCOPE_TOKEN_ENV = "MODELSCOPE_TOKEN"
MODELSCOPE_ACCESS_TOKEN_ENV = "MODELSCOPE_ACCESS_TOKEN"
AGENT_EXECUTION_TIMEOUT_ENV = "NEXUSAI_AGENT_EXECUTION_TIMEOUT_SECONDS"
AGENT_EXECUTION_FALLBACK_ENV = "NEXUSAI_AGENT_EXECUTION_FALLBACK"
AUTH_FILE_ENV = "NEXUSAI_AUTH_FILE"
AUTH_BOOTSTRAP_ADMIN_USERNAME_ENV = "NEXUSAI_AUTH_BOOTSTRAP_ADMIN_USERNAME"
AUTH_BOOTSTRAP_ADMIN_PASSWORD_ENV = "NEXUSAI_AUTH_BOOTSTRAP_ADMIN_PASSWORD"
AUTH_SESSION_TTL_HOURS_ENV = "NEXUSAI_AUTH_SESSION_TTL_HOURS"
DEFAULT_AGENT_EXECUTION_BASE_URL = "https://api-inference.modelscope.cn/v1"
DEFAULT_AGENT_EXECUTION_MODEL = "deepseek-ai/DeepSeek-V3.2"
DEFAULT_AGENT_EXECUTION_TIMEOUT_SECONDS = 45.0
DEFAULT_AUTH_BOOTSTRAP_ADMIN_USERNAME = "admin"
DEFAULT_AUTH_BOOTSTRAP_ADMIN_PASSWORD = "change-me-admin-password"
DEFAULT_AUTH_SESSION_TTL_HOURS = 24
SUPPORTED_AGENT_EXECUTION_FALLBACK = {"simulate", "fail"}
SUPPORTED_ARBITRATION_MODES = {"off", "judge_on_conflict", "judge_always"}
SUPPORTED_PIPELINE_ERROR_POLICIES = {"fail_fast", "continue"}
SUPPORTED_STORAGE_BACKENDS = {"json", "sqlite", "postgres"}
SUPPORTED_API_AUTH_ROLES = {"admin", "operator", "viewer"}
ROUTER_SKILL_WEIGHT_ENV = "NEXUSAI_ROUTER_SKILL_WEIGHT"
ROUTER_STATUS_WEIGHT_ENV = "NEXUSAI_ROUTER_STATUS_WEIGHT"
ROUTER_LOAD_PENALTY_ENV = "NEXUSAI_ROUTER_LOAD_PENALTY"
ROUTER_PRIORITY_STATUS_BONUS_LOW_ENV = "NEXUSAI_ROUTER_PRIORITY_STATUS_BONUS_LOW"
ROUTER_PRIORITY_STATUS_BONUS_MEDIUM_ENV = "NEXUSAI_ROUTER_PRIORITY_STATUS_BONUS_MEDIUM"
ROUTER_PRIORITY_STATUS_BONUS_HIGH_ENV = "NEXUSAI_ROUTER_PRIORITY_STATUS_BONUS_HIGH"

DEFAULT_ROUTER_POLICY: dict[str, Any] = {
    "policy_version": "v1",
    "skill_weight": 100,
    "status_weight": 10,
    "load_penalty": 1,
    "priority_status_bonus": {
        "low": 0,
        "medium": 2,
        "high": 6,
    },
}

_ENV_LOADED = False

ROLE_INSTRUCTION_TEMPLATES: dict[str, str] = {
    "planner": (
        "You are the Planner Agent. Break down the objective into pragmatic phases, "
        "highlight dependencies, and provide an execution order."
    ),
    "research": (
        "You are the Research Agent. Focus on evidence gathering, source quality, and concise findings."
    ),
    "analyst": (
        "You are the Analyst Agent. Evaluate trade-offs, risks, and assumptions with structured reasoning."
    ),
    "writer": (
        "You are the Writer Agent. Produce clear, actionable output with strong readability and concise format."
    ),
    "reviewer": (
        "You are the Reviewer Agent. Validate completeness, consistency, and potential failure points."
    ),
    "judge": (
        "You are the Judge Agent. Resolve conflicts between competing outputs and provide a final decision with rationale."
    ),
}

DEFAULT_DECOMPOSITION_TEMPLATE = "general"
DECOMPOSITION_TEMPLATES: dict[str, dict[str, Any]] = {
    "general": {
        "keywords": ["task", "work"],
        "steps": [
            "Clarify scope and success criteria",
            "Collect supporting information",
            "Analyze options and trade-offs",
            "Draft final response",
        ],
    },
    "research_report": {
        "keywords": ["research", "report", "summary", "analysis"],
        "steps": [
            "Define research questions",
            "Collect and organize evidence",
            "Synthesize findings",
            "Produce concise report",
        ],
    },
    "planning": {
        "keywords": ["plan", "roadmap", "milestone", "timeline"],
        "steps": [
            "Set scope and assumptions",
            "Identify milestones",
            "Sequence execution plan",
            "Draft implementation checklist",
        ],
    },
}


def _normalize_strategy(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in SUPPORTED_CONSENSUS_STRATEGIES:
        return normalized
    return None


def get_default_consensus_strategy() -> tuple[str, str | None]:
    raw = os.getenv(DEFAULT_CONSENSUS_ENV)
    normalized = _normalize_strategy(raw)
    if normalized:
        return normalized, None
    if raw:
        note = (
            f"Invalid default strategy '{raw}' in {DEFAULT_CONSENSUS_ENV}; "
            f"fallback to '{FALLBACK_CONSENSUS_STRATEGY}'."
        )
        return FALLBACK_CONSENSUS_STRATEGY, note
    return FALLBACK_CONSENSUS_STRATEGY, None


def resolve_consensus_strategy(metadata: Mapping[str, Any] | None) -> tuple[str, str | None]:
    task_raw = str(metadata.get("consensus_strategy")) if metadata and metadata.get("consensus_strategy") is not None else None
    task_normalized = _normalize_strategy(task_raw)
    if task_normalized:
        return task_normalized, None

    default_strategy, default_note = get_default_consensus_strategy()
    if task_raw:
        task_note = (
            f"Invalid task strategy '{task_raw}'; use default '{default_strategy}'."
        )
        if default_note:
            return default_strategy, f"{task_note} {default_note}"
        return default_strategy, task_note

    return default_strategy, default_note


def get_event_history_limit() -> int:
    raw = os.getenv(EVENT_HISTORY_LIMIT_ENV)
    if not raw:
        return DEFAULT_EVENT_HISTORY_LIMIT
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_EVENT_HISTORY_LIMIT
    if parsed < 100:
        return 100
    return parsed


def _parse_bool_env(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _strip_env_value(raw: str) -> str:
    candidate = raw.strip()
    if (candidate.startswith('"') and candidate.endswith('"')) or (
        candidate.startswith("'") and candidate.endswith("'")
    ):
        return candidate[1:-1].strip()
    return candidate


def load_env_files() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    backend_root = Path(__file__).resolve().parents[2]
    configured = os.getenv(ENV_FILE_ENV)
    candidates = [Path(configured).expanduser().resolve()] if configured else [backend_root / ".env", backend_root / ".env.local"]

    for candidate in candidates:
        if not candidate.exists() or not candidate.is_file():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            normalized_key = key.strip()
            if not normalized_key:
                continue
            os.environ.setdefault(normalized_key, _strip_env_value(value))

    _ENV_LOADED = True


def is_json_persistence_enabled() -> bool:
    return _parse_bool_env(os.getenv(JSON_PERSISTENCE_ENABLED_ENV), default=True)


def get_storage_backend() -> str:
    raw = os.getenv(STORAGE_BACKEND_ENV)
    if not raw:
        return "sqlite"
    normalized = raw.strip().lower()
    if normalized in SUPPORTED_STORAGE_BACKENDS:
        return normalized
    return "sqlite"


def get_postgres_dsn() -> str | None:
    raw = os.getenv(POSTGRES_DSN_ENV)
    if raw and raw.strip():
        return raw.strip()
    return None


def should_fallback_on_storage_error() -> bool:
    return _parse_bool_env(os.getenv(STORAGE_FALLBACK_ON_ERROR_ENV), default=True)


def get_storage_fallback_backend() -> str:
    raw = os.getenv(STORAGE_FALLBACK_BACKEND_ENV)
    if not raw:
        return "json"
    normalized = raw.strip().lower()
    if normalized in {"json", "sqlite"}:
        return normalized
    return "json"


def is_read_only_mode_enabled() -> bool:
    return _parse_bool_env(os.getenv(READ_ONLY_MODE_ENV), default=False)


def get_data_dir() -> Path:
    raw = os.getenv(DATA_DIR_ENV)
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_DATA_DIR


def get_sqlite_path() -> Path:
    raw = os.getenv(SQLITE_PATH_ENV)
    if raw:
        return Path(raw).expanduser().resolve()
    return get_data_dir() / "nexusai.db"


def get_tasks_file() -> Path:
    return get_data_dir() / "tasks.json"


def get_agents_file() -> Path:
    return get_data_dir() / "agents.json"


def get_events_file() -> Path:
    return get_data_dir() / "events.json"


def get_auth_file() -> Path:
    raw = os.getenv(AUTH_FILE_ENV)
    if raw:
        return Path(raw).expanduser().resolve()
    return get_data_dir() / "auth.json"


def get_auth_bootstrap_admin_username() -> str:
    raw = os.getenv(AUTH_BOOTSTRAP_ADMIN_USERNAME_ENV)
    if raw and raw.strip():
        return raw.strip()
    return DEFAULT_AUTH_BOOTSTRAP_ADMIN_USERNAME


def get_auth_bootstrap_admin_password() -> str:
    raw = os.getenv(AUTH_BOOTSTRAP_ADMIN_PASSWORD_ENV)
    if raw and raw.strip():
        return raw.strip()
    return DEFAULT_AUTH_BOOTSTRAP_ADMIN_PASSWORD


def get_auth_session_ttl_hours() -> int:
    raw = os.getenv(AUTH_SESSION_TTL_HOURS_ENV)
    if not raw:
        return DEFAULT_AUTH_SESSION_TTL_HOURS
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_AUTH_SESSION_TTL_HOURS
    if parsed < 1:
        return 1
    if parsed > 24 * 30:
        return 24 * 30
    return parsed


def is_seed_enabled() -> bool:
    return _parse_bool_env(os.getenv(SEED_ENABLED_ENV), default=False)


def is_seed_apply_if_empty() -> bool:
    return _parse_bool_env(os.getenv(SEED_APPLY_IF_EMPTY_ENV), default=True)


def get_seed_file() -> Path:
    raw = os.getenv(SEED_FILE_ENV)
    if raw:
        return Path(raw).expanduser().resolve()
    return get_data_dir() / "seed.example.json"


def is_debug_api_enabled() -> bool:
    return _parse_bool_env(os.getenv(DEBUG_API_ENABLED_ENV), default=False)


def is_api_auth_enabled() -> bool:
    return _parse_bool_env(os.getenv(API_AUTH_ENABLED_ENV), default=False)


def get_api_auth_keys() -> set[str]:
    raw = os.getenv(API_AUTH_KEYS_ENV)
    keys = {item.strip() for item in raw.split(",") if item.strip()} if raw else set()
    keys.update(get_api_key_roles().keys())
    return keys


def normalize_api_auth_role(role: str | None, default: str = "viewer") -> str:
    if not role:
        return default
    normalized = role.strip().lower()
    if normalized in SUPPORTED_API_AUTH_ROLES:
        return normalized
    return default


def get_default_api_auth_role() -> str:
    return normalize_api_auth_role(os.getenv(API_AUTH_DEFAULT_ROLE_ENV), default="viewer")


def get_api_key_roles() -> dict[str, str]:
    raw = os.getenv(API_AUTH_KEY_ROLES_ENV)
    if not raw:
        return {}

    default_role = get_default_api_auth_role()
    mapping: dict[str, str] = {}
    for item in raw.split(","):
        pair = item.strip()
        if not pair:
            continue
        key, separator, role = pair.partition(":")
        normalized_key = key.strip()
        if not normalized_key:
            continue
        if not separator:
            mapping[normalized_key] = default_role
            continue
        mapping[normalized_key] = normalize_api_auth_role(role, default=default_role)
    return mapping


def resolve_api_key_role(api_key: str | None) -> str | None:
    if not api_key:
        return None
    mapping = get_api_key_roles()
    if api_key in mapping:
        return mapping[api_key]
    if api_key in get_api_auth_keys():
        return get_default_api_auth_role()
    return None


def get_api_auth_exempt_paths() -> tuple[str, ...]:
    defaults = ("/", "/health", "/docs", "/openapi.json", "/redoc", "/ws")
    raw = os.getenv(API_AUTH_EXEMPT_PATHS_ENV)
    if not raw:
        return defaults
    parsed = tuple(item.strip() for item in raw.split(",") if item.strip())
    return parsed or defaults


def should_clear_on_startup() -> bool:
    return _parse_bool_env(os.getenv(STARTUP_CLEAR_ENABLED_ENV), default=False)


def clear_events_only_on_startup() -> bool:
    return _parse_bool_env(os.getenv(STARTUP_CLEAR_EVENTS_ONLY_ENV), default=False)


def restore_seed_on_startup() -> bool:
    return _parse_bool_env(os.getenv(STARTUP_CLEAR_RESTORE_SEED_ENV), default=False)


def get_agent_execution_base_url() -> str:
    raw = os.getenv(AGENT_EXECUTION_BASE_URL_ENV)
    if raw and raw.strip():
        return raw.strip()
    return DEFAULT_AGENT_EXECUTION_BASE_URL


def get_agent_execution_model() -> str:
    raw = os.getenv(AGENT_EXECUTION_MODEL_ENV)
    if raw and raw.strip():
        return raw.strip()
    return DEFAULT_AGENT_EXECUTION_MODEL


def get_agent_execution_api_key() -> str | None:
    direct = os.getenv(AGENT_EXECUTION_API_KEY_ENV)
    if direct and direct.strip():
        return direct.strip()
    modelscope_access = os.getenv(MODELSCOPE_ACCESS_TOKEN_ENV)
    if modelscope_access and modelscope_access.strip():
        return modelscope_access.strip()
    modelscope = os.getenv(MODELSCOPE_TOKEN_ENV)
    if modelscope and modelscope.strip():
        return modelscope.strip()
    return None


def get_agent_execution_timeout_seconds() -> float:
    raw = os.getenv(AGENT_EXECUTION_TIMEOUT_ENV)
    if not raw:
        return DEFAULT_AGENT_EXECUTION_TIMEOUT_SECONDS
    try:
        parsed = float(raw)
    except ValueError:
        return DEFAULT_AGENT_EXECUTION_TIMEOUT_SECONDS
    if parsed < 5:
        return 5.0
    return parsed


def get_agent_execution_fallback() -> str:
    raw = os.getenv(AGENT_EXECUTION_FALLBACK_ENV)
    if not raw:
        return "simulate"
    normalized = raw.strip().lower()
    if normalized in SUPPORTED_AGENT_EXECUTION_FALLBACK:
        return normalized
    return "simulate"


def get_role_instruction_template(role: str | None) -> str:
    if not role:
        return (
            "You are a collaborative AI agent in the NexusAI workflow system. "
            "Produce concise, actionable output and be explicit about assumptions."
        )
    normalized = role.strip().lower()
    return ROLE_INSTRUCTION_TEMPLATES.get(
        normalized,
        (
            "You are a collaborative AI agent in the NexusAI workflow system. "
            f"Your role is '{normalized}'. Produce concise, actionable output and be explicit about assumptions."
        ),
    )


def normalize_arbitration_mode(value: str | None, default: str = "off") -> str:
    if not value:
        return default
    normalized = value.strip().lower()
    if normalized in SUPPORTED_ARBITRATION_MODES:
        return normalized
    return default


def normalize_pipeline_error_policy(value: str | None, default: str = "fail_fast") -> str:
    if not value:
        return default
    normalized = value.strip().lower()
    if normalized in SUPPORTED_PIPELINE_ERROR_POLICIES:
        return normalized
    return default


def resolve_decomposition_template(metadata: Mapping[str, Any] | None, objective: str) -> tuple[str, list[str], list[str]]:
    requested = None
    if metadata and metadata.get("decomposition_template") is not None:
        requested = str(metadata.get("decomposition_template")).strip().lower()

    if requested and requested in DECOMPOSITION_TEMPLATES:
        template = DECOMPOSITION_TEMPLATES[requested]
        return requested, list(template["steps"]), []

    objective_text = objective.lower()
    best_name = DEFAULT_DECOMPOSITION_TEMPLATE
    best_matches: list[str] = []
    for name, template in DECOMPOSITION_TEMPLATES.items():
        if name == DEFAULT_DECOMPOSITION_TEMPLATE:
            continue
        keywords = [str(keyword).lower() for keyword in template.get("keywords", [])]
        matches = [keyword for keyword in keywords if keyword in objective_text]
        if len(matches) > len(best_matches):
            best_name = name
            best_matches = matches

    steps = list(DECOMPOSITION_TEMPLATES[best_name]["steps"])
    return best_name, steps, best_matches


def get_default_max_retries() -> int:
    raw = os.getenv(MAX_RETRIES_ENV)
    if not raw:
        return DEFAULT_MAX_RETRIES
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_MAX_RETRIES
    if parsed < 0:
        return 0
    return parsed


def resolve_max_retries(metadata: Mapping[str, Any] | None) -> int:
    if metadata and metadata.get("max_retries") is not None:
        try:
            parsed = int(metadata.get("max_retries"))
        except (TypeError, ValueError):
            return get_default_max_retries()
        if parsed < 0:
            return 0
        return parsed
    return get_default_max_retries()


def _parse_non_negative_int(value: object, default: int) -> int:
    try:
        candidate = value if isinstance(value, (str, bytes, bytearray, int, float)) else str(value)
        parsed = int(candidate)
    except (TypeError, ValueError):
        return default
    if parsed < 0:
        return default
    return parsed


def resolve_router_policy(metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    defaults = DEFAULT_ROUTER_POLICY
    env_policy: dict[str, Any] = {
        "policy_version": defaults["policy_version"],
        "skill_weight": _parse_non_negative_int(os.getenv(ROUTER_SKILL_WEIGHT_ENV), int(defaults["skill_weight"])),
        "status_weight": _parse_non_negative_int(os.getenv(ROUTER_STATUS_WEIGHT_ENV), int(defaults["status_weight"])),
        "load_penalty": _parse_non_negative_int(os.getenv(ROUTER_LOAD_PENALTY_ENV), int(defaults["load_penalty"])),
        "priority_status_bonus": {
            "low": _parse_non_negative_int(
                os.getenv(ROUTER_PRIORITY_STATUS_BONUS_LOW_ENV),
                int(defaults["priority_status_bonus"]["low"]),
            ),
            "medium": _parse_non_negative_int(
                os.getenv(ROUTER_PRIORITY_STATUS_BONUS_MEDIUM_ENV),
                int(defaults["priority_status_bonus"]["medium"]),
            ),
            "high": _parse_non_negative_int(
                os.getenv(ROUTER_PRIORITY_STATUS_BONUS_HIGH_ENV),
                int(defaults["priority_status_bonus"]["high"]),
            ),
        },
    }

    overrides = metadata.get("routing_policy") if metadata else None
    if not isinstance(overrides, Mapping):
        return env_policy

    resolved = dict(env_policy)
    resolved["skill_weight"] = _parse_non_negative_int(overrides.get("skill_weight"), int(env_policy["skill_weight"]))
    resolved["status_weight"] = _parse_non_negative_int(overrides.get("status_weight"), int(env_policy["status_weight"]))
    resolved["load_penalty"] = _parse_non_negative_int(overrides.get("load_penalty"), int(env_policy["load_penalty"]))

    bonus_overrides = overrides.get("priority_status_bonus")
    bonus = dict(env_policy["priority_status_bonus"])
    if isinstance(bonus_overrides, Mapping):
        bonus["low"] = _parse_non_negative_int(bonus_overrides.get("low"), int(bonus["low"]))
        bonus["medium"] = _parse_non_negative_int(bonus_overrides.get("medium"), int(bonus["medium"]))
        bonus["high"] = _parse_non_negative_int(bonus_overrides.get("high"), int(bonus["high"]))
    resolved["priority_status_bonus"] = bonus
    return resolved


load_env_files()


