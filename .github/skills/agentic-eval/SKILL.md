---
name: agentic-eval
description: |
  用于评估和改进 AI agent 输出的模式与技巧。适用于：
  - 实现自我批判和反思循环
  - 构建评估器-优化器（evaluator-optimizer）流水线以提升质量关键型生成结果
  - 创建测试驱动的代码精炼工作流
  - 设计基于评分标准（rubric）或 LLM-as-judge 的评估系统
  - 为 agent 输出添加迭代式改进能力（代码、报告、分析）
  - 衡量并提升 agent 响应质量
---

# Agentic Evaluation Patterns

通过迭代评估与精炼实现自我改进的模式。

## 概览

评估模式使 agent 能够评估并改进自己的输出，从单次生成升级为迭代式精炼循环。

```
生成 → 评估 → 批判 → 精炼 → 输出
    ↑                          │
    └──────────────────────────┘
```

## 何时使用

- **质量关键型生成**：代码、报告、分析等对准确性要求较高的内容
- **有明确评估标准的任务**：存在清晰的成功指标
- **需要特定标准的内容**：风格指南、合规性、格式要求

---

## 模式 1：基础反思

agent 通过自我批判来评估并改进自己的输出。

```python
def reflect_and_refine(task: str, criteria: list[str], max_iterations: int = 3) -> str:
    """通过反思循环生成结果。"""
    output = llm(f"完成这个任务：\n{task}")
    
    for i in range(max_iterations):
        # 自我批判
        critique = llm(f"""
        根据以下标准评估输出：{criteria}
        输出：{output}
        对每一项以 PASS/FAIL 形式给出反馈，结果为 JSON。
        """)
        
        critique_data = json.loads(critique)
        all_pass = all(c["status"] == "PASS" for c in critique_data.values())
        if all_pass:
            return output
        
        # 根据批判结果进行改进
        failed = {k: v["feedback"] for k, v in critique_data.items() if v["status"] == "FAIL"}
        output = llm(f"根据以下问题进行改进：{failed}\n原始内容：{output}")
    
    return output
```

**关键点**：使用结构化 JSON 输出，便于可靠地解析批判结果。

---

## 模式 2：评估器-优化器

将生成和评估拆分为独立组件，以便职责更清晰。

```python
class EvaluatorOptimizer:
    def __init__(self, score_threshold: float = 0.8):
        self.score_threshold = score_threshold
    
    def generate(self, task: str) -> str:
        return llm(f"完成：{task}")
    
    def evaluate(self, output: str, task: str) -> dict:
        return json.loads(llm(f"""
        评估输出是否符合任务：{task}
        输出：{output}
        返回 JSON：{{"overall_score": 0-1, "dimensions": {{"accuracy": ..., "clarity": ...}}}}
        """))
    
    def optimize(self, output: str, feedback: dict) -> str:
        return llm(f"根据以下反馈改进：{feedback}\n输出：{output}")
    
    def run(self, task: str, max_iterations: int = 3) -> str:
        output = self.generate(task)
        for _ in range(max_iterations):
            evaluation = self.evaluate(output, task)
            if evaluation["overall_score"] >= self.score_threshold:
                break
            output = self.optimize(output, evaluation)
        return output
```

---

## 模式 3：代码专用反思

面向代码生成的测试驱动精炼循环。

```python
class CodeReflector:
    def reflect_and_fix(self, spec: str, max_iterations: int = 3) -> str:
        code = llm(f"根据以下规格编写 Python 代码：{spec}")
        tests = llm(f"根据以下规格生成 pytest 测试：{spec}\n代码：{code}")
        
        for _ in range(max_iterations):
            result = run_tests(code, tests)
            if result["success"]:
                return code
            code = llm(f"修复这个错误：{result['error']}\n代码：{code}")
        return code
```

---

## 评估策略

### 基于结果

评估输出是否达到了预期结果。

```python
def evaluate_outcome(task: str, output: str, expected: str) -> str:
    return llm(f"输出是否达成预期结果？任务：{task}, 预期：{expected}, 输出：{output}")
```

### LLM-as-Judge

使用 LLM 对多个输出进行比较和排序。

```python
def llm_judge(output_a: str, output_b: str, criteria: str) -> str:
    return llm(f"根据以下标准比较 A 和 B 两个输出：{criteria}。哪个更好？为什么？")
```

### 基于评分标准（Rubric）

按加权维度对输出进行评分。

```python
RUBRIC = {
    "accuracy": {"weight": 0.4},
    "clarity": {"weight": 0.3},
    "completeness": {"weight": 0.3}
}

def evaluate_with_rubric(output: str, rubric: dict) -> float:
    scores = json.loads(llm(f"请为以下维度打 1-5 分：{list(rubric.keys())}\n输出：{output}"))
    return sum(scores[d] * rubric[d]["weight"] for d in rubric) / 5
```

---

## 最佳实践

| 实践 | 原因 |
|------|------|
| **清晰的评估标准** | 事先定义具体、可衡量的评估条件 |
| **迭代次数上限** | 设置最大迭代次数（3-5 次），避免无限循环 |
| **收敛检查** | 如果输出分数不再提升，则停止 |
| **记录历史** | 保留完整轨迹，便于调试和分析 |
| **结构化输出** | 使用 JSON 方便可靠解析评估结果 |

---

## 快速开始清单

```markdown
## 评估实现清单

### 设置
- [ ] 定义评估标准 / rubric
- [ ] 设置"足够好"的分数阈值
- [ ] 配置最大迭代次数（默认：3）

### 实现
- [ ] 实现 generate() 函数
- [ ] 实现带结构化输出的 evaluate() 函数
- [ ] 实现 optimize() 函数
- [ ] 连接精炼循环

### 安全性
- [ ] 添加收敛检测
- [ ] 记录所有迭代过程，便于调试
- [ ] 优雅处理评估解析失败
```