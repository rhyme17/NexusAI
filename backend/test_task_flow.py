#!/usr/bin/env python
"""测试脚本：验证任务创建和访问流程"""

import requests

BASE_URL = "http://localhost:8000"

def test_health():
    """检查后端服务是否正常"""
    print("🔍 检查后端服务...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ 后端服务正常")
            return True
        else:
            print(f"❌ 后端服务异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接后端: {e}")
        return False

def test_admin_login():
    """测试 admin 用户登录"""
    print("\n🔍 测试 admin 用户登录...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "hhx20060604"}
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print(f"✅ admin 登录成功")
            print(f"   用户: {data.get('user', {}).get('username')}")
            print(f"   角色: {data.get('user', {}).get('role')}")
            return token
        else:
            print(f"❌ admin 登录失败: {response.json()}")
            return None
    except Exception as e:
        print(f"❌ 登录请求异常: {e}")
        return None

def test_create_task(token):
    """测试创建任务"""
    print("\n🔍 测试创建任务...")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(
            f"{BASE_URL}/api/tasks",
            json={
                "objective": "测试任务：分析人工智能发展趋势",
                "priority": "medium",
                "metadata": {"source": "auto_discover", "test": True}
            },
            headers=headers
        )
        if response.status_code == 201:
            data = response.json()
            task_id = data.get("task_id")
            print(f"✅ 创建任务成功")
            print(f"   任务ID: {task_id}")
            print(f"   目标: {data.get('objective')}")
            print(f"   owner_user_id: {data.get('owner_user_id')}")
            return task_id
        else:
            print(f"❌ 创建任务失败: {response.json()}")
            return None
    except Exception as e:
        print(f"❌ 创建任务异常: {e}")
        return None

def test_get_task(token, task_id):
    """测试获取任务"""
    print(f"\n🔍 测试获取任务 {task_id}...")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(
            f"{BASE_URL}/api/tasks/{task_id}",
            headers=headers
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 获取任务成功")
            print(f"   任务ID: {data.get('task_id')}")
            print(f"   目标: {data.get('objective')}")
            print(f"   owner_user_id: {data.get('owner_user_id')}")
            print(f"   metadata: {data.get('metadata')}")
            return True
        else:
            print(f"❌ 获取任务失败: {response.status_code} - {response.json()}")
            return False
    except Exception as e:
        print(f"❌ 获取任务异常: {e}")
        return False

def test_list_tasks(token):
    """测试获取任务列表"""
    print("\n🔍 测试获取任务列表...")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{BASE_URL}/api/tasks", headers=headers)
        if response.status_code == 200:
            tasks = response.json()
            print(f"✅ 获取任务列表成功")
            print(f"   任务数量: {len(tasks)}")
            for task in tasks[:5]:
                print(f"   • {task.get('task_id')}: {task.get('objective')[:50]}...")
            return tasks
        else:
            print(f"❌ 获取任务列表失败: {response.json()}")
            return []
    except Exception as e:
        print(f"❌ 获取任务列表异常: {e}")
        return []

def test_auto_discover_run(token):
    """测试自动发现执行"""
    print("\n🔍 测试自动发现执行...")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(
            f"{BASE_URL}/api/auto-discover/run",
            headers=headers
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 自动发现执行成功")
            print(f"   新闻数量: {data.get('news_count')}")
            print(f"   问题数量: {data.get('problems_count')}")
            print(f"   创建任务: {data.get('tasks_created')}")
            for task in data.get('tasks', []):
                print(f"   • {task.get('task_id')}: {task.get('objective')}")
            return data.get('tasks', [])
        else:
            print(f"❌ 自动发现执行失败: {response.json()}")
            return []
    except Exception as e:
        print(f"❌ 自动发现执行异常: {e}")
        return []

def main():
    print("="*60)
    print("🚀 NexusAI 任务创建和访问测试")
    print("="*60)
    
    # 检查后端服务
    if not test_health():
        return
    
    # 登录 admin 用户
    token = test_admin_login()
    if not token:
        return
    
    # 创建测试任务
    task_id = test_create_task(token)
    if task_id:
        # 获取任务
        test_get_task(token, task_id)
    
    # 获取任务列表
    test_list_tasks(token)
    
    # 执行自动发现
    auto_tasks = test_auto_discover_run(token)
    if auto_tasks:
        # 尝试获取自动发现创建的任务
        for task in auto_tasks:
            test_get_task(token, task.get('task_id'))

if __name__ == "__main__":
    main()