from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime

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


def _get_agent():
    global _agent_instance
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


@router.get("/config", response_model=AutoDiscoverConfig)
def get_config() -> AutoDiscoverConfig:
    """获取自动发现配置"""
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
    """更新自动发现配置"""
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
    """获取已发现的新闻列表"""
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
                news_item = NewsItem(
                    title=item.get("title", ""),
                    link=item.get("link", ""),
                    description=item.get("description", ""),
                    source_name=source["name"],
                    category=source["category"],
                    pub_date=item.get("pub_date"),
                )
                if category is None or news_item.category == category:
                    all_news.append(news_item)
        except Exception:
            continue
    
    return NewsListResponse(
        items=all_news[:limit],
        total=len(all_news),
        sources=list(sources),
    )


@router.get("/problems", response_model=ProblemListResponse)
def get_problems(limit: int = 20, problem_type: str | None = None) -> ProblemListResponse:
    """获取已发现的问题列表"""
    agent = _get_agent()
    
    problems = agent.discovered_problems if agent.discovered_problems else []
    
    if problem_type:
        problems = [p for p in problems if p.get("type") == problem_type]
    
    items = []
    for p in problems[:limit]:
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
        total=len(problems),
    )


@router.post("/fetch-news", response_model=NewsListResponse)
def fetch_news() -> NewsListResponse:
    """立即获取最新新闻（不创建任务）"""
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
                news_item = NewsItem(
                    title=item.get("title", ""),
                    link=item.get("link", ""),
                    description=item.get("description", ""),
                    source_name=source["name"],
                    category=source["category"],
                    pub_date=item.get("pub_date"),
                )
                all_news.append(news_item)
        except Exception:
            continue
    
    return NewsListResponse(
        items=all_news[:100],
        total=len(all_news),
        sources=list(sources),
    )


@router.post("/run", response_model=AutoDiscoverRunResult)
def run_immediate() -> AutoDiscoverRunResult:
    """立即执行自动发现（忽略速率限制，用于演示）"""
    agent = _get_agent()
    result = agent.run_immediate()
    return AutoDiscoverRunResult(**result)


@router.get("/status", response_model=AutoDiscoverStatus)
def get_status() -> AutoDiscoverStatus:
    """获取自动发现状态"""
    RateConfig = _get_rate_config()
    config = RateConfig.load()
    agent = _get_agent()
    
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
        news_count=len(agent.discovered_problems) if agent.discovered_problems else 0,
        problems_count=len(agent.discovered_problems) if agent.discovered_problems else 0,
    )


@router.post("/enable")
def enable_auto_discover() -> dict[str, str]:
    """启用自动发现"""
    RateConfig = _get_rate_config()
    config = RateConfig.load()
    config.enabled = True
    config.save()
    return {"status": "enabled"}


@router.post("/disable")
def disable_auto_discover() -> dict[str, str]:
    """禁用自动发现"""
    RateConfig = _get_rate_config()
    config = RateConfig.load()
    config.enabled = False
    config.save()
    return {"status": "disabled"}


@router.get("/sources")
def get_sources() -> list[dict[str, str]]:
    """获取新闻源列表"""
    import sys
    from pathlib import Path
    backend_path = Path(__file__).resolve().parents[2]
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from auto_discover import NEWS_SOURCES
    return NEWS_SOURCES
