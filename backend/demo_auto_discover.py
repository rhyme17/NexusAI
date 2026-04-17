#!/usr/bin/env python
"""
NexusAI 自主发现功能演示脚本

演示 AI 自动发现问题并提交任务的完整流程
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_discover import AutoDiscoverAgent, NexusAIClient


def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║                NexusAI 自主发现功能演示                                  ║
╚══════════════════════════════════════════════════════════════════════════╝

本演示展示如何实现完全无人类干预的 AI 自主工作循环：

    🔍 自动浏览新闻 → 🧠 AI分析发现问题 → 📝 生成任务 → 🚀 提交系统

──────────────────────────────────────────────────────────────────────────
""")
    
    # 首先检查后端状态
    client = NexusAIClient()
    if not client.health_check():
        print("❌ 后端服务未运行！")
        print("   请先启动后端服务:")
        print("   cd backend && uvicorn app.main:app --reload")
        sys.exit(1)
    
    print("✅ 后端服务已就绪")
    print()
    
    # 获取现有任务
    print("📋 当前系统任务情况:")
    recent_tasks = client.get_recent_tasks(limit=5)
    if recent_tasks:
        for i, task in enumerate(recent_tasks, 1):
            print(f"   [{i}] {task['objective'][:50]}... ({task['status']})")
    else:
        print("   暂无任务")
    
    print()
    print("🚀 启动自主问题发现器...")
    print()
    
    # 运行发现器
    agent = AutoDiscoverAgent()
    agent.run()
    
    print("""
──────────────────────────────────────────────────────────────────────────
✨ 演示完成！

实现完全无人类干预的关键组件：

1. 🔍 新闻获取器 (NewsFetcher)
   - 支持多个RSS源
   - 自动解析新闻内容

2. 🧠 问题分析器 (ProblemAnalyzer)
   - 智能识别问题类型
   - 优先级自动计算
   - 去重和排序

3. 📝 任务生成器 (TaskGenerator)
   - 问题→任务转换
   - 智能模板匹配
   - 元数据记录

4. 🚀 NexusAI客户端 (NexusAIClient)
   - REST API对接
   - 任务状态追踪

🔄 持续运行：
   python auto_discover.py --continuous --interval 30

这将每30分钟自动检查新闻，发现问题并提交任务，实现真正的无人工干预！
──────────────────────────────────────────────────────────────────────────
""")


if __name__ == "__main__":
    main()