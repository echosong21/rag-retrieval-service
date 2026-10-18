"""校验 golden set 的 JSON 合法性与字段完整性（一次性检查脚本）。"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

p = Path(__file__).parent / "golden_questions.json"
data = json.loads(p.read_text(encoding="utf-8"))

print("JSON 合法: OK")
print("题目数:", len(data))
print("形态分布:", dict(Counter(x["form"] for x in data)))

ids = [x["id"] for x in data]
print("id 唯一:", len(ids) == len(set(ids)))

required = ("id", "question", "form", "expected_source")
bad = [x.get("id", "?") for x in data if any(not x.get(k) for k in required)]
print("必填字段完整:", "OK" if not bad else f"MISSING {bad}")

print()
print("id  | form      | question                       | expected_source[0]")
print("-" * 100)
for x in data:
    print(f"{x['id']:>3} | {x['form']:<9} | {x['question'][:28]:<30} | {x['expected_source'][0][:36]}")