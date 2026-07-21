"""
QualityEvaluatorAgent 双层评估集成测试
验证：硬校验失败时 pass 被强制为 false，rule_issues 被合并进 evaluation。

mock LLM 直接顶掉 call_llm。
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.quality_agent import QualityEvaluatorAgent  # noqa: E402


def _make_agent():
    agent = QualityEvaluatorAgent(llm_client=MagicMock())
    return agent


def _world_view():
    return {
        "summary": "玄幻世界",
        "world_view": {"rules": "灵气不能逆练"},
        "story_framework": {"conflict": "复仇"},
        "characters": [
            {"name": "林凡"}, {"name": "苏婉儿"}, {"name": "掌门"},
        ],
    }


def _chapter_outline():
    return {
        "summary": "林凡发现苏婉儿留下的书信",
        "key_events": ["林凡读到书信", "苏婉儿离去"],
        "characters_present": ["林凡", "苏婉儿"],
        "cliffhanger": "苏婉儿赴死",
        "foreshadowing": [],
    }


def _gen_text(chars):
    body = "天地灵气充盈于山林之间修士打坐吐坐修炼。" * (chars // 16 + 1)
    return body[:chars]


# ----------------------------------------------------------------------
#  测试 1：硬校验失败（字数严重不足），LLM 给的 pass=true 会被强制 false
# ----------------------------------------------------------------------

def test_hard_issue_overrides_llm_pass():
    agent = _make_agent()
    # mock LLM 返回 pass=true high score
    agent.call_llm = MagicMock(return_value=json.dumps({
        "overall_score": 8.5, "dimensions": {},
        "issues": [], "highlights": [], "summary": "ok",
        "pass": True, "needs_revision": False,
    }, ensure_ascii=False))

    # content 只有 300 字，target_length=3000 → word_count hard fail
    content = _gen_text(300)
    out = agent.run({
        "content": content,
        "title": "第1章",
        "chapter_index": 1,
        "world_view": _world_view(),
        "chapter_outline": _chapter_outline(),
        "summary": "",
        "target_length": 3000,
    })

    assert out["pass"] is False, "硬校验失败时应强制 pass=false"
    assert out["needs_revision"] is True
    assert out["rule_hard_count"] >= 1
    # 硬校验 issues 必须出现在 evaluation.issues 里
    assert any(i.get("source") == "rule_checker" for i in out["issues"]), \
        "rule_issues 应被合并进 evaluation.issues"
    # 统计字段齐备
    assert "rule_stats" in out
    assert "rule_pass" in out


# ----------------------------------------------------------------------
#  测试 2：LLM 自己也判 fail → 仍然 false（正常情况）
# ----------------------------------------------------------------------

def test_llm_fail_still_fails():
    agent = _make_agent()
    agent.call_llm = MagicMock(return_value=json.dumps({
        "overall_score": 5.0, "dimensions": {},
        "issues": [{"type": "logic", "description": "bad", "suggestion": "fix"}],
        "highlights": [], "summary": "poor",
        "pass": False, "needs_revision": True,
    }, ensure_ascii=False))

    content = _gen_text(3000)   # 字数 OK
    out = agent.run({
        "content": content,
        "title": "第2章",
        "chapter_index": 2,
        "world_view": _world_view(),
        "chapter_outline": {},    # 简化 outline
        "summary": "",
        "target_length": 3000,
    })
    assert out["pass"] is False


# ----------------------------------------------------------------------
#  测试 3：LLM pass + 无硬校验问题 → pass=true 未被改写
# ----------------------------------------------------------------------

def test_no_rule_issue_llm_pass_preserved():
    agent = _make_agent()
    agent.call_llm = MagicMock(return_value=json.dumps({
        "overall_score": 8.0, "dimensions": {},
        "issues": [], "highlights": [], "summary": "good",
        "pass": True, "needs_revision": False,
    }, ensure_ascii=False))

    content = "林凡回到洞府，发现苏婉儿留下的书信。他展开细读。"
    content += _gen_text(3000)
    content += "谁也没想到，她此去竟是赴死之旅。"

    out = agent.run({
        "content": content,
        "title": "第3章",
        "chapter_index": 3,
        "world_view": _world_view(),
        "chapter_outline": _chapter_outline(),
        "summary": "",
        "target_length": 3000,
    })
    # 字数接近、结尾带问号/引导词、关键事件有人名锚定
    # 大概率 pass=true（只要没有硬校验 fail）
    # 我们只断言 LLM 的 pass=true 没有被错误覆盖
    if out["rule_pass"]:
        assert out["pass"] is True, "rule 全过 + LLM pass=true 时应为 pass=true"


# ----------------------------------------------------------------------
#  测试 4：禁用句式被规则捕获，且 pass=false
# ----------------------------------------------------------------------

def test_forbidden_phrase_triggers_hard():
    agent = _make_agent()
    agent.call_llm = MagicMock(return_value=json.dumps({
        "overall_score": 9.0, "dimensions": {},
        "issues": [], "highlights": [], "summary": "great",
        "pass": True, "needs_revision": False,
    }, ensure_ascii=False))

    content = "第一章 风起" + _gen_text(3000)  # 章标题标记
    out = agent.run({
        "content": content,
        "title": "第4章",
        "chapter_index": 4,
        "world_view": _world_view(),
        "chapter_outline": {},
        "summary": "",
        "target_length": 3000,
    })
    assert out["pass"] is False
    assert any(i["type"] == "forbidden_phrase" and i["source"] == "rule_checker"
               for i in out["issues"])


# ----------------------------------------------------------------------
#  测试 5：LLM 解析失败不会让 pipeline 崩溃，仍给出错误 evaluation
# ----------------------------------------------------------------------

def test_llm_json_parse_failure_still_returns():
    agent = _make_agent()
    agent.call_llm = MagicMock(return_value="完全不是JSON")

    content = _gen_text(3000)
    out = agent.run({
        "content": content,
        "title": "第5章",
        "chapter_index": 5,
        "world_view": _world_view(),
        "chapter_outline": {},
        "summary": "",
        "target_length": 3000,
    })
    # 应该返回带 error 的 evaluation，pass=false
    assert "error" in out
    assert out["pass"] is False
    # 错误路径也要把 rule_issues 带出来
    assert "rule_issues" in out


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
        except AssertionError:
            failed += 1
            import traceback; traceback.print_exc()
            print(f"  FAIL {t.__name__}")
        except Exception as e:
            failed += 1
            import traceback; traceback.print_exc()
            print(f"  ERROR {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(0 if failed == 0 else 1)
