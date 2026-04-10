#!/usr/bin/env python
"""
NexusAI 后端完整演示脚本

演示功能：
  1. 创建任务 + 查看分解
  2. Agent 失败执行 + 重试
  3. Agent 成功执行
  4. 查看事件历史
  5. 查看尝试历史
"""

import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000"


def print_section(title):
    """打印分隔符"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def main():
    print_section("NexusAI 后端完整演示")
    print("\n📍 确保后端已启动: uvicorn app.main:app --reload")

    try:
        # 1. 健康检查
        print_section("1️⃣  健康检查")
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ 后端未启动，请先运行: uvicorn app.main:app --reload")
            sys.exit(1)
        print(f"✅ 后端健康: {response.json()}")

        # 2. 列出预定义 Agent
        print_section("2️⃣  列出预定义 Agent")
        response = requests.get(f"{BASE_URL}/api/agents")
        agents = response.json()
        print(f"✅ 总共 {len(agents)} 个 Agent:")
        for agent in agents:
            print(f"   • {agent['agent_id']:20s} {agent['role']:15s} skills: {', '.join(agent['skills'])}")

        # 3. 注册自定义 Agent
        print_section("3️⃣  注册自定义 Agent")
        custom_agent = {
            "name": "demo-judge",
            "role": "judge",
            "skills": ["decision", "arbitration"],
            "metadata": {"demo": True}
        }
        response = requests.post(f"{BASE_URL}/api/agents", json=custom_agent)
        new_agent = response.json()
        print(f"✅ 注册成功: {new_agent['agent_id']}")
        print(f"   名称: {new_agent['name']}, 角色: {new_agent['role']}")

        # 4. 创建任务（带拆解）
        print_section("4️⃣  创建任务 + 查看拆解")
        task_payload = {
            "objective": "分析 AI 智能体协作框架的商业价值和技术方案",
            "priority": "high",
            "metadata": {
                "decomposition_template": "research_report",
                "consensus_strategy": "majority_vote",
                "max_retries": 2
            }
        }
        response = requests.post(f"{BASE_URL}/api/tasks", json=task_payload)
        task = response.json()
        task_id = task["task_id"]

        print(f"✅ 任务创建成功")
        print(f"   任务 ID: {task_id}")
        print(f"   状态: {task['status']}")
        print(f"   进度: {task['progress']}%")
        print(f"   分配 Agent: {task['assigned_agent_ids']}")

        # 查看拆解
        decomposition = task['metadata'].get('decomposition', {})
        if decomposition:
            print(f"\n📋 任务拆解 (模板: {decomposition['template']}):")
            for step in decomposition['subtasks']:
                assigned = step.get('assigned_agent_id', '未分配')
                print(f"   [{step['step_id']}] {step['title']}")
                print(f"       ↳ 分配给: {assigned}")

        # 5. 模拟 Agent 执行失败
        print_section("5️⃣  模拟 Agent 执行（失败）")
        sim_fail = {
            "mode": "failure",
            "error_message": "数据检索 API 超时",
            "simulate_handoff": False
        }
        response = requests.post(f"{BASE_URL}/api/tasks/{task_id}/simulate", json=sim_fail)
        failed_task = response.json()
        print(f"✅ 执行模拟完成")
        print(f"   状态: {failed_task['status']}")
        print(f"   进度: {failed_task['progress']}%")
        print(f"   结果: {failed_task['result']}")

        # 6. 查看失败事件
        print_section("6️⃣  查看任务事件历史")
        response = requests.get(f"{BASE_URL}/api/tasks/{task_id}/events?limit=5&sort=asc")
        events = response.json()
        print(f"✅ 任务事件 (共 {len(events)} 条，显示前 5 条):")
        for event in events:
            ts = event['timestamp'][-8:]  # 只显示时间部分
            print(f"   [{event['type']:20s}] {event['sender']:20s} @ {ts}")

        # 7. 重试失败的任务
        print_section("7️⃣  重试失败的任务")
        retry_payload = {
            "reason": "网络延迟，重新尝试",
            "requeue": True
        }
        response = requests.post(f"{BASE_URL}/api/tasks/{task_id}/retry", json=retry_payload)
        if response.status_code == 200:
            retried = response.json()
            print(f"✅ 重试成功")
            print(f"   重试次数: {retried['retry_count']}")
            print(f"   新状态: {retried['status']}")
        else:
            print(f"❌ 重试失败: {response.json()['detail']}")

        time.sleep(0.5)

        # 8. 模拟再次执行（这次成功）
        print_section("8️⃣  模拟 Agent 执行（成功）")
        sim_success = {
            "mode": "success",
            "progress_points": [30, 70]
        }
        response = requests.post(f"{BASE_URL}/api/tasks/{task_id}/simulate", json=sim_success)
        final_task = response.json()
        print(f"✅ 执行模拟完成")
        print(f"   状态: {final_task['status']}")
        print(f"   进度: {final_task['progress']}%")
        print(f"   结果: {final_task['result']}")

        # 9. 查看尝试历史
        print_section("9️⃣  查看任务尝试历史")
        response = requests.get(f"{BASE_URL}/api/tasks/{task_id}/attempts")
        attempts = response.json()
        print(f"✅ 尝试历史")
        print(f"   重试次数: {attempts['retry_count']} / {attempts['max_retries']}")
        print(f"   尝试记录:")
        for item in attempts['items']:
            outcome = item['outcome']
            symbol = "❌" if outcome == "failed" else "🔄" if outcome == "retried" else "✅"
            print(f"     {symbol} 尝试 #{item['attempt_number']}: {outcome}")
            if item['reason']:
                print(f"        └─ {item['reason']}")

        # 10. 获取最终结果
        print_section("🔟 获取最终结果")
        response = requests.get(f"{BASE_URL}/api/tasks/{task_id}/result")
        result = response.json()
        print(f"✅ 任务结果")
        print(f"   任务 ID: {result['task_id']}")
        print(f"   状态: {result['status']}")
        print(f"   结果: {json.dumps(result['result'], indent=6, ensure_ascii=False)}")

        # 11. 创建冲突场景（多 Agent 不同意见）
        print_section("1️⃣1️⃣  演示冲突检测与仲裁")
        conflict_task = {
            "objective": "评估新产品上市时间",
            "priority": "high",
            "metadata": {
                "consensus_strategy": "majority_vote"
            }
        }
        response = requests.post(f"{BASE_URL}/api/tasks", json=conflict_task)
        conf_task = response.json()
        conf_id = conf_task["task_id"]
        print(f"✅ 创建冲突场景任务: {conf_id}")

        # Agent 1 提议方案 A
        update1 = {
            "status": "in_progress",
            "progress": 50,
            "agent_id": "agent_planner",
            "confidence": 0.7,
            "result": {"recommendation": "立即上市 (30 天)"}
        }
        requests.patch(f"{BASE_URL}/api/tasks/{conf_id}/status", json=update1)
        print(f"   • Agent 1 意见: 立即上市 (置信度 0.7)")

        # Agent 2 提议方案 B
        update2 = {
            "status": "completed",
            "progress": 100,
            "agent_id": "agent_analyst",
            "confidence": 0.85,
            "result": {"recommendation": "延后上市 (60 天)"}
        }
        response = requests.patch(f"{BASE_URL}/api/tasks/{conf_id}/status", json=update2)
        conf_final = response.json()
        print(f"   • Agent 2 意见: 延后上市 (置信度 0.85)")

        # 查看仲裁结果
        if conf_final.get('consensus'):
            consensus = conf_final['consensus']
            print(f"\n⚖️  仲裁结果:")
            print(f"   冲突检测: {consensus['conflict_detected']}")
            print(f"   决策方式: {consensus['decided_by']}")
            print(f"   最终决议: {consensus['decision_result']['recommendation']}")
            print(f"   原因: {consensus['reason']}")

        # 12. 总结
        print_section("✨ 演示完成")
        print("""
✅ 已演示的功能：
   • Agent 注册与列表管理
   • 任务创建与自动拆解（4 步工作流）
   • Agent 模拟执行（成功/失败）
   • 失败重试与恢复
   • 尝试历史追踪
   • 事件流查询
   • 多 Agent 冲突检测
   • 共识仲裁（多数投票）

📊 API 总结：
   • 14+ REST 接口
   • 11 种事件类型
   • 5 个预定义 Agent
   • 39 个单元测试 ✅

📖 更多信息：
   • API 文档: http://localhost:8000/docs
   • 后端说明: backend/README.md
   • 根目录: README.md
        """)

    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到后端!")
        print("   请先运行: uvicorn app.main:app --reload")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

