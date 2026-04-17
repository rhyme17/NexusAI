#!/usr/bin/env python
"""
NexusAI 自主问题发现器

功能：
  1. 自动浏览新闻源，检索信息
  2. 使用AI分析发现现实问题
  3. 生成需要解决的任务
  4. 自动提交到 NexusAI 系统

实现完全无人类干预的 AI 自主工作循环

隔离方案：使用系统用户 auto_discoverer 创建任务，并标记来源
"""

import requests
import json
import time
import random
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field

# 配置
BASE_URL = "http://localhost:8000"
SYSTEM_USER = "auto_discoverer"
SYSTEM_PASSWORD = "nexusai-auto-discover-system-user"

# 默认速率配置
DEFAULT_NEWS_RATE_SECONDS = 60      # 新闻读取间隔（秒）
DEFAULT_TASK_RATE_MINUTES = 60      # 任务产生间隔（分钟）
DEFAULT_MAX_TASKS_PER_RUN = 3       # 每次最多创建任务数

# 配置文件路径
CONFIG_FILE = Path(__file__).parent / "config" / "auto_discover_config.json"

# 新闻源配置
NEWS_SOURCES = [
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "technology"},
    {"name": "Hacker News", "url": "https://news.ycombinator.com/rss", "category": "technology"},
    {"name": "BBC News", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "category": "world"},
    {"name": "CNN", "url": "http://rss.cnn.com/rss/edition.rss", "category": "general"},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/", "category": "technology"},
]

# 问题类型模板（中英文关键词）
PROBLEM_TEMPLATES = [
    {"type": "opportunity", "keywords": ["突破", "创新", "新发现", "革命性", "颠覆性", "机遇", 
                                         "breakthrough", "innovation", "discovery", "revolutionary", 
                                         "opportunity", "launch", "raise", "funding", "growth"]},
    {"type": "problem", "keywords": ["危机", "问题", "挑战", "失败", "风险", "短缺", "紧急", 
                                     "crisis", "problem", "challenge", "fail", "risk", "shortage", 
                                     "urgent", "warning", "issue", "threat"]},
    {"type": "trend", "keywords": ["趋势", "增长", "下降", "预测", "未来", "发展",
                                    "trend", "growth", "decline", "predict", "future", "develop",
                                    "increase", "decrease", "forecast"]},
    {"type": "conflict", "keywords": ["冲突", "争议", "矛盾", "对立", "分歧",
                                       "conflict", "controversy", "dispute", "oppose", "divide"]},
    {"type": "innovation", "keywords": ["AI", "人工智能", "机器学习", "自动化", "量子", "区块链",
                                         "artificial intelligence", "machine learning", "automation", 
                                         "quantum", "blockchain", "robotics", "deep learning"]},
]


@dataclass
class RateConfig:
    """速率配置"""
    news_rate_seconds: int = DEFAULT_NEWS_RATE_SECONDS
    task_rate_minutes: int = DEFAULT_TASK_RATE_MINUTES
    max_tasks_per_run: int = DEFAULT_MAX_TASKS_PER_RUN
    enabled: bool = True
    
    @classmethod
    def load(cls) -> "RateConfig":
        """从配置文件加载"""
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                return cls(
                    news_rate_seconds=data.get("news_rate_seconds", DEFAULT_NEWS_RATE_SECONDS),
                    task_rate_minutes=data.get("task_rate_minutes", DEFAULT_TASK_RATE_MINUTES),
                    max_tasks_per_run=data.get("max_tasks_per_run", DEFAULT_MAX_TASKS_PER_RUN),
                    enabled=data.get("enabled", True),
                )
            except Exception:
                pass
        return cls()
    
    def save(self) -> None:
        """保存到配置文件"""
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "news_rate_seconds": self.news_rate_seconds,
            "task_rate_minutes": self.task_rate_minutes,
            "max_tasks_per_run": self.max_tasks_per_run,
            "enabled": self.enabled,
        }
        CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class NewsFetcher:
    """新闻获取器"""
    
    def __init__(self, rate_seconds: int = DEFAULT_NEWS_RATE_SECONDS):
        self.rate_seconds = rate_seconds
        self.last_fetch_time = None
        self._skip_rate_limit = False
    
    def skip_rate_limit(self, skip: bool = True) -> "NewsFetcher":
        """设置是否跳过速率限制"""
        self._skip_rate_limit = skip
        return self
    
    def _fetch_raw(self, url: str) -> str:
        """获取RSS原始内容"""
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    
    def fetch_rss_feed(self, url: str) -> List[Dict[str, str]]:
        """获取RSS feed内容（带速率限制）"""
        if not self._skip_rate_limit and self.last_fetch_time:
            elapsed = (datetime.now() - self.last_fetch_time).total_seconds()
            if elapsed < self.rate_seconds:
                wait_time = self.rate_seconds - elapsed
                print(f"   ⏳ 速率限制：等待 {wait_time:.1f} 秒...")
                time.sleep(wait_time)
        
        try:
            self.last_fetch_time = datetime.now()
            content = self._fetch_raw(url)
            return self._parse_rss(content)
        except Exception as e:
            print(f"❌ 获取新闻失败 {url}: {e}")
            return []
    
    @staticmethod
    def _parse_rss(content: str) -> List[Dict[str, str]]:
        """简单解析RSS内容"""
        items = []
        import re
        
        item_pattern = r'<item>(.*?)</item>'
        matches = re.findall(item_pattern, content, re.DOTALL)
        
        for match in matches:
            title = re.search(r'<title>(.*?)</title>', match)
            link = re.search(r'<link>(.*?)</link>', match)
            description = re.search(r'<description>(.*?)</description>', match)
            
            if title and link:
                items.append({
                    "title": title.group(1).strip(),
                    "link": link.group(1).strip(),
                    "description": description.group(1).strip() if description else ""
                })
        
        return items


class ProblemAnalyzer:
    """问题分析器 - 使用AI分析内容发现问题"""
    
    def __init__(self):
        self.problem_types = PROBLEM_TEMPLATES
    
    def analyze_content(self, items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """分析新闻内容，发现潜在问题和机会"""
        problems = []
        
        for item in items:
            combined_text = f"{item['title']} {item['description']}"
            
            for template in self.problem_types:
                for keyword in template["keywords"]:
                    if keyword.lower() in combined_text.lower():
                        problem = self._generate_problem(item, template["type"], keyword)
                        if problem:
                            problems.append(problem)
                        break
        
        unique_problems = self._deduplicate(problems)
        return sorted(unique_problems, key=lambda x: x["priority"], reverse=True)
    
    def _generate_problem(self, item: Dict[str, str], problem_type: str, keyword: str) -> Dict[str, Any]:
        """根据内容生成问题描述"""
        urgency = self._calculate_urgency(item["title"], problem_type)
        
        problem = {
            "title": item["title"],
            "source": item["link"],
            "type": problem_type,
            "keyword_found": keyword,
            "priority": urgency,
            "description": self._generate_description(item, problem_type),
            "timestamp": datetime.now().isoformat()
        }
        
        return problem
    
    def _calculate_urgency(self, title: str, problem_type: str) -> int:
        """计算问题紧急程度"""
        urgency = 50
        
        urgent_keywords = ["紧急", "危机", "立即", "严重", "突发", "警告",
                          "urgent", "crisis", "immediate", "severe", "breaking", 
                          "warning", "critical", "emergency"]
        for word in urgent_keywords:
            if word.lower() in title.lower():
                urgency += 30
        
        type_bonus = {
            "problem": 20,
            "opportunity": 15,
            "conflict": 25,
            "trend": 10,
            "innovation": 15
        }
        
        urgency += type_bonus.get(problem_type, 0)
        return min(urgency, 100)
    
    def _generate_description(self, item: Dict[str, str], problem_type: str) -> str:
        """生成问题描述"""
        type_descriptions = {
            "problem": f"检测到潜在问题：{item['title']}。需要分析影响范围和解决方案。",
            "opportunity": f"发现新机遇：{item['title']}。值得深入研究和评估可行性。",
            "trend": f"识别到趋势变化：{item['title']}。需要跟踪发展动态。",
            "conflict": f"发现冲突/争议：{item['title']}。需要分析各方立场和可能的解决方案。",
            "innovation": f"发现创新技术：{item['title']}。值得研究其应用前景和商业价值。"
        }
        
        return type_descriptions.get(problem_type, f"分析主题：{item['title']}")
    
    def _deduplicate(self, problems: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重问题列表"""
        seen = set()
        unique = []
        for p in problems:
            key = f"{p['title']}_{p['type']}"
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique


class TaskGenerator:
    """任务生成器 - 将问题转化为NexusAI任务"""
    
    @staticmethod
    def generate_tasks(problems: List[Dict[str, Any]], limit: int = DEFAULT_MAX_TASKS_PER_RUN) -> List[Dict[str, Any]]:
        """根据问题生成任务"""
        tasks = []
        
        for problem in problems[:limit]:
            task = TaskGenerator._create_task(problem)
            if task:
                tasks.append(task)
        
        return tasks
    
    @staticmethod
    def _create_task(problem: Dict[str, Any]) -> Dict[str, Any]:
        """创建单个任务"""
        task_templates = {
            "problem": {
                "objective": f"分析并解决问题：{problem['title']}",
                "description": problem["description"],
                "template": "research_report"
            },
            "opportunity": {
                "objective": f"评估商业机会：{problem['title']}",
                "description": problem["description"],
                "template": "research_report"
            },
            "trend": {
                "objective": f"分析趋势发展：{problem['title']}",
                "description": problem["description"],
                "template": "research_report"
            },
            "conflict": {
                "objective": f"分析冲突并提出解决方案：{problem['title']}",
                "description": problem["description"],
                "template": "research_report"
            },
            "innovation": {
                "objective": f"研究创新技术应用：{problem['title']}",
                "description": problem["description"],
                "template": "research_report"
            }
        }
        
        template = task_templates.get(problem["type"], task_templates["problem"])
        
        return {
            "objective": template["objective"],
            "priority": "high" if problem["priority"] >= 70 else "medium",
            "metadata": {
                "decomposition_template": template["template"],
                "consensus_strategy": "majority_vote",
                "max_retries": 2,
                "source": "auto_discover",
                "auto_discovered": True,
                "source_url": problem["source"],
                "problem_type": problem["type"],
                "discovery_time": problem["timestamp"],
                "created_by_system": True,
            }
        }


class NexusAIClient:
    """NexusAI API客户端 - 支持系统用户认证"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.auth_token: Optional[str] = None
        self.user_info: Optional[Dict[str, Any]] = None
    
    def health_check(self) -> bool:
        """检查后端是否正常运行"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def login_as_system_user(self) -> bool:
        """以系统用户身份登录"""
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={"username": SYSTEM_USER, "password": SYSTEM_PASSWORD},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.user_info = data.get("user")
                print(f"✅ 已以系统用户 '{SYSTEM_USER}' 身份登录")
                return True
            else:
                print(f"⚠️ 系统用户登录失败，将以匿名方式创建任务")
                return False
        except Exception as e:
            print(f"⚠️ 登录异常: {e}，将以匿名方式创建任务")
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    def create_task(self, task_payload: Dict[str, Any]) -> Dict[str, Any] | None:
        """创建任务"""
        try:
            response = requests.post(
                f"{self.base_url}/api/tasks",
                json=task_payload,
                headers=self._get_headers(),
                timeout=30
            )
            if response.status_code == 201:
                return response.json()
            print(f"❌ 创建任务失败: {response.json()}")
            return None
        except Exception as e:
            print(f"❌ 创建任务异常: {e}")
            return None
    
    def get_recent_tasks(self, limit: int = 10, source: str | None = None) -> List[Dict[str, Any]]:
        """获取最近任务"""
        try:
            response = requests.get(
                f"{self.base_url}/api/tasks",
                headers=self._get_headers()
            )
            if response.status_code == 200:
                tasks = response.json()
                if source:
                    tasks = [t for t in tasks if t.get("metadata", {}).get("source") == source]
                return sorted(tasks, key=lambda x: x["created_at"], reverse=True)[:limit]
            return []
        except Exception as e:
            print(f"❌ 获取任务列表失败: {e}")
            return []
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "news_rate_seconds": RateConfig.load().news_rate_seconds,
            "task_rate_minutes": RateConfig.load().task_rate_minutes,
            "max_tasks_per_run": RateConfig.load().max_tasks_per_run,
            "enabled": RateConfig.load().enabled,
        }
    
    def update_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """更新配置"""
        rate_config = RateConfig.load()
        if "news_rate_seconds" in config:
            rate_config.news_rate_seconds = max(10, int(config["news_rate_seconds"]))
        if "task_rate_minutes" in config:
            rate_config.task_rate_minutes = max(1, int(config["task_rate_minutes"]))
        if "max_tasks_per_run" in config:
            rate_config.max_tasks_per_run = max(1, min(10, int(config["max_tasks_per_run"])))
        if "enabled" in config:
            rate_config.enabled = bool(config["enabled"])
        rate_config.save()
        return {
            "news_rate_seconds": rate_config.news_rate_seconds,
            "task_rate_minutes": rate_config.task_rate_minutes,
            "max_tasks_per_run": rate_config.max_tasks_per_run,
            "enabled": rate_config.enabled,
        }


class AutoDiscoverAgent:
    """自主发现代理 - 整合所有组件"""
    
    def __init__(self, config: RateConfig | None = None):
        self.config = config or RateConfig.load()
        self.news_fetcher = NewsFetcher(rate_seconds=self.config.news_rate_seconds)
        self.analyzer = ProblemAnalyzer()
        self.task_generator = TaskGenerator()
        self.client = NexusAIClient()
        
        self.last_check_time: Optional[datetime] = None
        self.last_task_time: Optional[datetime] = None
        self.discovered_problems: List[Dict[str, Any]] = []
        self.created_tasks: List[Dict[str, Any]] = []
        
        self._running = False
        self._stop_event = threading.Event()
    
    def can_create_task(self) -> bool:
        """检查是否可以创建新任务（基于速率限制）"""
        if not self.last_task_time:
            return True
        elapsed = (datetime.now() - self.last_task_time).total_seconds() / 60
        return elapsed >= self.config.task_rate_minutes
    
    def run(self, force: bool = False) -> Dict[str, Any]:
        """执行完整的发现流程
        
        Args:
            force: 是否强制执行（忽略速率限制）
        """
        result = {
            "success": False,
            "news_count": 0,
            "problems_count": 0,
            "tasks_created": 0,
            "tasks": [],
            "message": ""
        }
        
        print(f"\n{'='*70}")
        print(f"🤖 NexusAI 自主问题发现器 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        if not self.config.enabled and not force:
            print("ℹ️ 自动发现功能已禁用")
            result["message"] = "自动发现功能已禁用"
            return result
        
        if not self.client.health_check():
            print("❌ 后端服务未运行，请先启动: uvicorn app.main:app --reload")
            result["message"] = "后端服务未运行"
            return result
        
        print("✅ 后端服务正常")
        
        self.client.login_as_system_user()
        
        if not force and not self.can_create_task():
            wait_minutes = self.config.task_rate_minutes - (datetime.now() - self.last_task_time).total_seconds() / 60
            print(f"⏳ 任务速率限制：需等待 {wait_minutes:.1f} 分钟")
            result["message"] = f"任务速率限制：需等待 {wait_minutes:.1f} 分钟"
            return result
        
        print("\n📡 正在获取新闻源...")
        all_news = []
        for source in NEWS_SOURCES:
            print(f"   🔍 {source['name']} ({source['category']})")
            items = self.news_fetcher.fetch_rss_feed(source["url"])
            for item in items:
                item["source_name"] = source["name"]
                item["category"] = source["category"]
            all_news.extend(items)
        
        print(f"   ✅ 获取到 {len(all_news)} 条新闻")
        result["news_count"] = len(all_news)
        
        print("\n🧠 正在分析内容发现问题...")
        problems = self.analyzer.analyze_content(all_news)
        self.discovered_problems = problems
        
        if not problems:
            print("   ℹ️ 未发现需要处理的问题")
            result["message"] = "未发现需要处理的问题"
            return result
        
        print(f"   ✅ 发现 {len(problems)} 个潜在问题/机会")
        result["problems_count"] = len(problems)
        for i, problem in enumerate(problems[:5], 1):
            print(f"      [{i}] [{problem['type']}] {problem['title']} (优先级: {problem['priority']})")
        
        print("\n📝 正在生成任务...")
        tasks = self.task_generator.generate_tasks(problems, limit=self.config.max_tasks_per_run)
        
        if not tasks:
            print("   ℹ️ 未生成任何任务")
            result["message"] = "未生成任何任务"
            return result
        
        print(f"   ✅ 生成 {len(tasks)} 个任务")
        
        print("\n🚀 正在提交任务到 NexusAI...")
        for task_payload in tasks:
            result_task = self.client.create_task(task_payload)
            if result_task:
                self.created_tasks.append(result_task)
                result["tasks"].append(result_task)
                print(f"   ✅ 创建任务成功: {result_task['task_id']}")
                print(f"      目标: {result_task['objective']}")
                print(f"      来源: auto_discover (系统用户: {SYSTEM_USER})")
            else:
                print(f"   ❌ 创建任务失败: {task_payload['objective']}")
        
        result["tasks_created"] = len(result["tasks"])
        result["success"] = True
        result["message"] = f"成功创建 {len(result['tasks'])} 个任务"
        
        self.last_check_time = datetime.now()
        self.last_task_time = datetime.now()
        
        print("\n📊 本次运行总结")
        print(f"   • 检查新闻源: {len(NEWS_SOURCES)} 个")
        print(f"   • 获取新闻: {len(all_news)} 条")
        print(f"   • 发现问题: {len(problems)} 个")
        print(f"   • 生成任务: {len(tasks)} 个")
        print(f"   • 成功提交: {len(result['tasks'])} 个")
        print(f"   • 任务来源: auto_discover (系统用户: {SYSTEM_USER})")
        
        return result
    
    def run_immediate(self) -> Dict[str, Any]:
        """立即执行（忽略速率限制，用于演示）"""
        print("\n⚡ 立即执行模式（忽略速率限制）")
        self.news_fetcher._skip_rate_limit = True
        return self.run(force=True)
    
    def start_continuous_monitoring(self) -> None:
        """启动持续监控模式"""
        print(f"\n🔄 启动持续监控模式")
        print(f"   • 新闻读取间隔: {self.config.news_rate_seconds} 秒")
        print(f"   • 任务产生间隔: {self.config.task_rate_minutes} 分钟")
        print(f"   • 每次最多任务: {self.config.max_tasks_per_run} 个")
        print("   按 Ctrl+C 停止")
        
        self._running = True
        self._stop_event.clear()
        
        try:
            while self._running and not self._stop_event.is_set():
                self.run()
                
                wait_time = self.config.task_rate_minutes * 60
                print(f"\n⏳ 等待 {self.config.task_rate_minutes} 分钟后再次检查...")
                
                for _ in range(int(wait_time)):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\n👋 监控已停止")
        finally:
            self._running = False
    
    def stop(self) -> None:
        """停止监控"""
        self._running = False
        self._stop_event.set()


def print_intro():
    """打印介绍信息"""
    intro = """
╔══════════════════════════════════════════════════════════════════════════╗
║                    NexusAI 自主问题发现器                               ║
╚══════════════════════════════════════════════════════════════════════════╝

这个脚本实现了 AI 自主发现问题的闭环系统：

┌─────────────────────────────────────────────────────────────────────┐
│  🔍 新闻获取 → 🧠 AI分析 → 📝 生成任务 → 🚀 自动提交              │
└─────────────────────────────────────────────────────────────────────┘

隔离方案：
  • 系统用户: auto_discoverer
  • 任务来源: metadata.source = "auto_discover"
  • 可通过用户/来源过滤区分人工任务和自动任务

功能特点：
  • 自动浏览多个新闻源（TechCrunch, BBC, CNN等）
  • 智能分析内容，识别问题类型（机会/问题/趋势/冲突/创新）
  • 自动生成优先级排序的任务
  • 无缝对接 NexusAI 任务系统
  • 支持速率控制配置
  • 支持持续监控模式

运行模式：
  1. 单次运行: python auto_discover.py
  2. 立即执行（演示）: python auto_discover.py --immediate
  3. 持续监控: python auto_discover.py --continuous
  4. 配置速率: python auto_discover.py --config

──────────────────────────────────────────────────────────────────────────
"""
    print(intro)


def main():
    import argparse
    
    print_intro()
    
    parser = argparse.ArgumentParser(description="NexusAI 自主问题发现器")
    parser.add_argument("--continuous", action="store_true", help="启动持续监控模式")
    parser.add_argument("--immediate", action="store_true", help="立即执行（忽略速率限制，用于演示）")
    parser.add_argument("--interval", type=int, default=None, help="持续监控间隔（分钟）")
    parser.add_argument("--config", action="store_true", help="显示/修改配置")
    parser.add_argument("--news-rate", type=int, help="设置新闻读取间隔（秒）")
    parser.add_argument("--task-rate", type=int, help="设置任务产生间隔（分钟）")
    parser.add_argument("--max-tasks", type=int, help="设置每次最多创建任务数")
    parser.add_argument("--enable", action="store_true", help="启用自动发现")
    parser.add_argument("--disable", action="store_true", help="禁用自动发现")
    
    args = parser.parse_args()
    
    config = RateConfig.load()
    
    if args.news_rate:
        config.news_rate_seconds = max(10, args.news_rate)
        config.save()
        print(f"✅ 新闻读取间隔已设置为 {config.news_rate_seconds} 秒")
    
    if args.task_rate:
        config.task_rate_minutes = max(1, args.task_rate)
        config.save()
        print(f"✅ 任务产生间隔已设置为 {config.task_rate_minutes} 分钟")
    
    if args.max_tasks:
        config.max_tasks_per_run = max(1, min(10, args.max_tasks))
        config.save()
        print(f"✅ 每次最多创建任务数已设置为 {config.max_tasks_per_run}")
    
    if args.enable:
        config.enabled = True
        config.save()
        print("✅ 自动发现功能已启用")
    
    if args.disable:
        config.enabled = False
        config.save()
        print("✅ 自动发现功能已禁用")
    
    if args.config:
        print("\n📋 当前配置:")
        print(f"   • 新闻读取间隔: {config.news_rate_seconds} 秒")
        print(f"   • 任务产生间隔: {config.task_rate_minutes} 分钟")
        print(f"   • 每次最多任务: {config.max_tasks_per_run} 个")
        print(f"   • 功能状态: {'启用' if config.enabled else '禁用'}")
        print(f"   • 配置文件: {CONFIG_FILE}")
        return
    
    if args.interval:
        config.task_rate_minutes = args.interval
        config.save()
    
    agent = AutoDiscoverAgent(config=config)
    
    if args.immediate:
        agent.run_immediate()
    elif args.continuous:
        agent.start_continuous_monitoring()
    else:
        agent.run()


if __name__ == "__main__":
    main()
