#!/usr/bin/env python
"""
快速启动脚本 - 启动后端 + 运行演示
"""

import subprocess
import time
import sys
import os

def main():
    print("=" * 70)
    print("  NexusAI 后端启动 + 演示")
    print("=" * 70)
    
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = script_dir if os.path.basename(script_dir) == "backend" else os.path.join(script_dir, "backend")
    
    print(f"\n📍 后端目录: {backend_dir}")
    
    # 启动 FastAPI 后端
    print("\n🚀 启动 FastAPI 后端...")
    uvicorn_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    print("   ⏳ 等待后端启动（3 秒）...")
    time.sleep(3)
    
    # 检查后端是否启动成功
    if uvicorn_process.poll() is not None:
        print("   ❌ 后端启动失败!")
        sys.exit(1)
    
    print("   ✅ 后端已启动在 http://localhost:8000")
    print("   📖 API 文档: http://localhost:8000/docs")
    
    # 运行演示脚本
    print("\n🎬 运行演示脚本...")
    print("-" * 70)
    
    try:
        result = subprocess.run(
            [sys.executable, "demo.py"],
            cwd=backend_dir,
            text=True,
        )
        
        print("-" * 70)
        if result.returncode == 0:
            print("\n✅ 演示完成!")
        else:
            print(f"\n⚠️  演示以代码 {result.returncode} 结束")
    
    except KeyboardInterrupt:
        print("\n\n⏹️  用户中断")
    
    finally:
        print("\n🛑 关闭后端...")
        uvicorn_process.terminate()
        try:
            uvicorn_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            uvicorn_process.kill()
        print("   ✅ 后端已关闭")

if __name__ == "__main__":
    main()

