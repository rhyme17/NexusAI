import requests
import json

tasks = requests.get("http://localhost:8000/api/tasks").json()
print(f"总任务数: {len(tasks)}")
for t in tasks:
    source = t.get("metadata", {}).get("source", "human")
    owner = t.get("owner_username", "anonymous")
    print(f"  {t['task_id']}: source={source}, owner={owner}")
    print(f"    {t['objective'][:60]}...")
