import time
import threading
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from typing import Any

router = APIRouter(prefix="/api/auto-discover", tags=["auto-discover"])


class AutoDiscoverConfig(BaseModel):
    news_rate_seconds: int = Field(default=60, ge=10, description="新闻读取间隔（秒）")
    task_rate_minutes: int = Field(default=60, ge=1, description="任务产生间隔（分钟）")
    max_tasks_per_run: int = Field(default=3, ge=1, le=10, description="每次最多创建任务数")
    enabled: bool = Field(default=True, description="是否启用自动发现")


class NewsItem(BaseModel):
    title: str
    link: str
    description: str
    source_name: str
    category: str
    pub_date: str | None = None


class ProblemItem(BaseModel):
    title: str
    source: str
    type: str
    keyword_found: str
    priority: int
    description: str
    timestamp: str
    source_name: str | None = None
    category: str | None = None


class AutoDiscoverRunResult(BaseModel):
    success: bool
    news_count: int
    problems_count: int
    tasks_created: int
    tasks: list[dict[str, Any]]
    message: str


class AutoDiscoverStatus(BaseModel):
    enabled: bool
    running: bool
    last_run_time: str | None
    last_task_time: str | None
    config: AutoDiscoverConfig
    news_count: int = 0
    problems_count: int = 0


class NewsListResponse(BaseModel):
    items: list[NewsItem]
    total: int
    sources: list[str]


class ProblemListResponse(BaseModel):
    items: list[ProblemItem]
    total: int


_agent_instance = None
_agent_lock = threading.Lock()

_cached_news: list[dict[str, Any]] = []
_cached_news_time: float = 0
_cached_problems: list[dict[str, Any]] = []
_NEWS_CACHE_TTL = 300


def _get_agent():
    global _agent_instance
    with _agent_lock:
        if _agent_instance is None:
            import sys
            from pathlib import Path
            backend_path = Path(__file__).resolve().parents[2]
            if str(backend_path) not in sys.path:
                sys.path.insert(0, str(backend_path))
            from auto_discover import AutoDiscoverAgent, RateConfig
            config = RateConfig.load()
            _agent_instance = AutoDiscoverAgent(config=config)
        return _agent_instance


def _get_rate_config():
    import sys
    from pathlib import Path
    backend_path = Path(__file__).resolve().parents[2]
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from auto_discover import RateConfig
    return RateConfig


def _fetch_all_news() -> tuple[list[dict[str, Any]], set[str]]:
    import sys
    from pathlib import Path
    backend_path = Path(__file__).resolve().parents[2]
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from auto_discover import NEWS_SOURCES, NewsFetcher

    fetcher = NewsFetcher(rate_seconds=0).skip_rate_limit(True)
    all_news = []
    sources = set()

    for source in NEWS_SOURCES:
        sources.add(source["name"])
        try:
            items = fetcher._parse_rss(fetcher._fetch_raw(source["url"]))
            for item in items:
                all_news.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "description": item.get("description", ""),
                    "source_name": source["name"],
                    "category": source["category"],
                    "pub_date": item.get("pub_date"),
                })
        except Exception:
            continue

    return all_news, sources


def _get_cached_news(force_refresh: bool = False) -> tuple[list[dict[str, Any]], set[str]]:
    global _cached_news, _cached_news_time

    now = time.time()
    if not force_refresh and _cached_news and (now - _cached_news_time) < _NEWS_CACHE_TTL:
        sources = {item["source_name"] for item in _cached_news}
        return _cached_news, sources

    all_news, sources = _fetch_all_news()
    _cached_news = all_news
    _cached_news_time = now
    return all_news, sources


@router.get("/config", response_model=AutoDiscoverConfig)
def get_config() -> AutoDiscoverConfig:
    RateConfig = _get_rate_config()
    config = RateConfig.load()
    return AutoDiscoverConfig(
        news_rate_seconds=config.news_rate_seconds,
        task_rate_minutes=config.task_rate_minutes,
        max_tasks_per_run=config.max_tasks_per_run,
        enabled=config.enabled,
    )


@router.patch("/config", response_model=AutoDiscoverConfig)
def update_config(payload: AutoDiscoverConfig) -> AutoDiscoverConfig:
    RateConfig = _get_rate_config()
    config = RateConfig.load()
    config.news_rate_seconds = payload.news_rate_seconds
    config.task_rate_minutes = payload.task_rate_minutes
    config.max_tasks_per_run = payload.max_tasks_per_run
    config.enabled = payload.enabled
    config.save()

    global _agent_instance
    if _agent_instance:
        _agent_instance.config = config

    return AutoDiscoverConfig(
        news_rate_seconds=config.news_rate_seconds,
        task_rate_minutes=config.task_rate_minutes,
        max_tasks_per_run=config.max_tasks_per_run,
        enabled=config.enabled,
    )


@router.get("/news", response_model=NewsListResponse)
def get_news(limit: int = 50, category: str | None = None) -> NewsListResponse:
    all_news, sources = _get_cached_news()

    if category:
        all_news = [n for n in all_news if n.get("category") == category]

    items = [NewsItem(**n) for n in all_news[:limit]]
    return NewsListResponse(
        items=items,
        total=len(all_news),
        sources=list(sources),
    )


@router.get("/problems", response_model=ProblemListResponse)
def get_problems(limit: int = 20, problem_type: str | None = None) -> ProblemListResponse:
    agent = _get_agent()

    problems = agent.discovered_problems if agent.discovered_problems else []
    global _cached_problems
    if problems:
        _cached_problems = problems

    display_problems = _cached_problems if _cached_problems else problems

    if problem_type:
        display_problems = [p for p in display_problems if p.get("type") == problem_type]

    items = []
    for p in display_problems[:limit]:
        items.append(ProblemItem(
            title=p.get("title", ""),
            source=p.get("source", ""),
            type=p.get("type", ""),
            keyword_found=p.get("keyword_found", ""),
            priority=p.get("priority", 50),
            description=p.get("description", ""),
            timestamp=p.get("timestamp", ""),
            source_name=p.get("source_name"),
            category=p.get("category"),
        ))

    return ProblemListResponse(
        items=items,
        total=len(display_problems),
    )


@router.post("/fetch-news", response_model=NewsListResponse)
def fetch_news() -> NewsListResponse:
    all_news, sources = _get_cached_news(force_refresh=True)

    agent = _get_agent()
    if all_news and not agent.discovered_problems:
        from auto_discover import ProblemAnalyzer
        analyzer = ProblemAnalyzer()
        agent.discovered_problems = analyzer.analyze_content(all_news)

    items = [NewsItem(**n) for n in all_news[:100]]
    return NewsListResponse(
        items=items,
        total=len(all_news),
        sources=list(sources),
    )


@router.post("/run", response_model=AutoDiscoverRunResult)
def run_immediate(request: Request) -> AutoDiscoverRunResult:
    agent = _get_agent()
    result = agent.run_immediate()

    if result.get("success") and result.get("news_count", 0) > 0:
        global _cached_news, _cached_news_time
        all_news, _ = _fetch_all_news()
        _cached_news = all_news
        _cached_news_time = time.time()

    return AutoDiscoverRunResult(**result)


@router.get("/tasks")
def get_auto_discover_tasks(request: Request, limit: int = 20) -> list[dict[str, Any]]:
    from ..services.store import get_store
    store = get_store()
    all_tasks = store.list_tasks()

    auto_tasks = [
        t for t in all_tasks
        if t.metadata and t.metadata.get("source") == "auto_discover"
    ]
    auto_tasks.sort(key=lambda t: t.created_at, reverse=True)

    results = []
    for task in auto_tasks[:limit]:
        results.append({
            "task_id": task.task_id,
            "objective": task.objective,
            "priority": task.priority.value if hasattr(task.priority, "value") else str(task.priority),
            "status": task.status.value if hasattr(task.status, "value") else str(task.status),
            "progress": task.progress,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "metadata": task.metadata,
        })
    return results


@router.get("/status", response_model=AutoDiscoverStatus)
def get_status() -> AutoDiscoverStatus:
    RateConfig = _get_rate_config()
    config = RateConfig.load()
    agent = _get_agent()

    problems = agent.discovered_problems if agent.discovered_problems else []

    return AutoDiscoverStatus(
        enabled=config.enabled,
        running=agent._running,
        last_run_time=agent.last_check_time.isoformat() if agent.last_check_time else None,
        last_task_time=agent.last_task_time.isoformat() if agent.last_task_time else None,
        config=AutoDiscoverConfig(
            news_rate_seconds=config.news_rate_seconds,
            task_rate_minutes=config.task_rate_minutes,
            max_tasks_per_run=config.max_tasks_per_run,
            enabled=config.enabled,
        ),
        news_count=len(_cached_news),
        problems_count=len(problems),
    )


@router.post("/enable")
def enable_auto_discover() -> dict[str, str]:
    RateConfig = _get_rate_config()
    config = RateConfig.load()
    config.enabled = True
    config.save()
    return {"status": "enabled"}


@router.post("/disable")
def disable_auto_discover() -> dict[str, str]:
    RateConfig = _get_rate_config()
    config = RateConfig.load()
    config.enabled = False
    config.save()
    return {"status": "disabled"}


@router.get("/sources")
def get_sources() -> list[dict[str, str]]:
    import sys
    from pathlib import Path
    backend_path = Path(__file__).resolve().parents[2]
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from auto_discover import NEWS_SOURCES
    return NEWS_SOURCES
