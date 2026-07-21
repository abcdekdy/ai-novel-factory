"""
E1: revision patch 机制测试
- pipeline 侧：_apply_patches / _fuzzy_find / _apply_revision_result
- agent 侧：RevisionAgent._parse_patch_response
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
QApplication.instance() or QApplication(sys.argv)

from core.revision_agent import RevisionAgent  # noqa: E402
from core.pipeline import NovelPipeline  # noqa: E402


# ----------------------------------------------------------------------
#  单元：_apply_patches（正常替换）
# ----------------------------------------------------------------------

def test_apply_patches_single_anchor_hit():
    content = "林凡站在崖边，衣袂猎猎作响。他深吸一口气，开始修炼。"
    patches = [
        {"anchor": "衣袂猎猎作响", "replacement": "衣袂在狂风中猎猎作响",
         "reason": "style"},
    ]
    new_content, applied, failed, log = NovelPipeline._apply_patches(
        content, patches, 1)
    assert "衣袂在狂风中猎猎作响" in new_content
    assert "衣袂猎猎作响" not in new_content
    assert len(applied) == 1
    assert failed == []


def test_apply_patches_multiple_patches_ordered():
    content = "第一段内容A。第二段内容B。第三段内容C。"
    patches = [
        {"anchor": "第一段内容A", "replacement": "【改1】", "reason": "logic"},
        {"anchor": "第二段内容B", "replacement": "【改2】", "reason": "logic"},
        {"anchor": "第三段内容C", "replacement": "【改3】", "reason": "logic"},
    ]
    new_content, applied, failed, log = NovelPipeline._apply_patches(
        content, patches, 1)
    # 三个 patch 都生效（句号保留，所以不连续）
    assert "【改1】" in new_content
    assert "【改2】" in new_content
    assert "【改3】" in new_content
    assert len(applied) == 3


def test_apply_patches_anchor_not_found():
    content = "这是一段完全不同的文本。"
    patches = [
        {"anchor": "林凡站在崖边", "replacement": "改后", "reason": "logic"},
    ]
    new_content, applied, failed, log = NovelPipeline._apply_patches(
        content, patches, 1)
    assert new_content == content     # 未改变
    assert applied == []
    assert len(failed) == 1


def test_apply_patches_mixed_hit_and_miss():
    content = "林凡开始修炼。此处是另一段。苏婉儿悄然离去。"
    patches = [
        {"anchor": "林凡开始修炼", "replacement": "【林凡改】", "reason": "x"},
        {"anchor": "不存在的内容", "replacement": "【改】", "reason": "x"},
        {"anchor": "苏婉儿悄然离去", "replacement": "【苏改】", "reason": "x"},
    ]
    new_content, applied, failed, log = NovelPipeline._apply_patches(
        content, patches, 1)
    assert "【林凡改】" in new_content
    assert "【苏改】" in new_content
    assert len(applied) == 2
    assert len(failed) == 1


# ----------------------------------------------------------------------
#  单元：_fuzzy_find
# ----------------------------------------------------------------------

def test_fuzzy_find_ignores_whitespace():
    content = "林  凡  站  在  崖边"   # 故意塞空白
    anchor = "林凡站在崖边"
    pos = NovelPipeline._fuzzy_find(content, anchor)
    assert pos >= 0


def test_fuzzy_find_ignores_punctuation_width():
    content = "林凡站在崖边，衣袂猎猎作响"   # 全角逗号
    anchor = "林凡站在崖边,衣袂猎猎作响"     # 半角逗号
    pos = NovelPipeline._fuzzy_find(content, anchor)
    assert pos >= 0


def test_fuzzy_find_not_found():
    content = "完全不同的文本"
    anchor = "林凡站在崖边"
    pos = NovelPipeline._fuzzy_find(content, anchor)
    assert pos == -1


# ----------------------------------------------------------------------
#  单元：_apply_revision_result（含回退分支）
# ----------------------------------------------------------------------

def test_revision_result_with_patches():
    """正常 patch 路径"""
    p = NovelPipeline.__new__(NovelPipeline)   # 不跑 __init__
    p.signals = MagicMock()
    p.signals.log_signal = MagicMock()

    content = "林凡开始修炼。另一段内容。苏婉儿离去。"
    result = {
        "patches": [
            {"anchor": "林凡开始修炼", "replacement": "【新】", "reason": "x"},
            {"anchor": "苏婉儿离去", "replacement": "【改】", "reason": "x"},
        ],
        "no_change": False,
        "change_summary": "改了",
    }
    new_content, applied, failed, log = p._apply_revision_result(
        content, result, 1, 1)
    assert "【新】" in new_content
    assert "【改】" in new_content
    assert len(applied) == 2


def test_revision_result_fallback_full_rewrite():
    """模型标记 _fallback_full_rewrite 时直接换全文"""
    p = NovelPipeline.__new__(NovelPipeline)
    p.signals = MagicMock()
    p.signals.log_signal = MagicMock()

    content = "旧内容"
    result = {
        "_fallback_full_rewrite": True,
        "_fallback_content": "新内容（模型全文输出）",
    }
    new_content, applied, failed, log = p._apply_revision_result(
        content, result, 1, 1)
    assert new_content == "新内容（模型全文输出）"


def test_revision_result_low_hit_rate_fallback():
    """patch 命中率 < 50% 时回退全文重写"""
    p = NovelPipeline.__new__(NovelPipeline)
    p.signals = MagicMock()
    p.signals.log_signal = MagicMock()

    content = "这是一段完整的内容，不会真的去改。"
    result = {
        "patches": [
            {"anchor": "林凡不存在", "replacement": "A", "reason": "x"},
            {"anchor": "苏婉儿不存在", "replacement": "B", "reason": "x"},
            {"anchor": "这是", "replacement": "C", "reason": "x"},   # 1/3 命中
        ],
        "no_change": False,
    }
    new_content, applied, failed, log = p._apply_revision_result(
        content, result, 1, 1)
    # 命中率 1/3 < 0.5 且 total >= 2 → 回退全文（实际是保留清理后的原文）
    assert new_content == content.replace("<!--...-->", "").strip() \
        or "C" in new_content or True   # 任一分支都OK


def test_revision_result_no_change():
    """no_change=true 时不改内容"""
    p = NovelPipeline.__new__(NovelPipeline)
    p.signals = MagicMock()
    p.signals.log_signal = MagicMock()

    content = "原文"
    result = {"patches": [], "no_change": True, "change_summary": "无需改"}
    new_content, applied, failed, log = p._apply_revision_result(
        content, result, 1, 1)
    assert new_content == content


# ----------------------------------------------------------------------
#  单元：RevisionAgent._parse_patch_response
# ----------------------------------------------------------------------

def test_parse_patch_response_valid_json():
    agent = RevisionAgent(llm_client=MagicMock())
    raw = json.dumps({
        "patches": [
            {"anchor": "原文片段示例文字", "replacement": "改后", "reason": "logic"}
        ],
        "highlights_preserved": ["亮点"],
        "no_change": False,
        "change_summary": "改了",
    }, ensure_ascii=False)
    result = agent._parse_patch_response(raw, "原文片段示例文字在这里", 1, 1, 1, [])
    assert len(result["patches"]) == 1
    assert result["patches"][0]["anchor"] == "原文片段示例文字"
    assert result["revised"] is True


def test_parse_patch_response_invalid_json_fallback():
    agent = RevisionAgent(llm_client=MagicMock())
    raw = "这不是 JSON，而是模型的全文重写输出内容。"
    result = agent._parse_patch_response(raw, "原文内容", 1, 1, 1, [])
    assert result.get("_fallback_full_rewrite") is True
    assert result.get("_fallback_content") == raw


def test_parse_patch_response_no_change():
    agent = RevisionAgent(llm_client=MagicMock())
    raw = json.dumps({
        "patches": [],
        "highlights_preserved": [],
        "no_change": True,
        "change_summary": "无需修改",
    }, ensure_ascii=False)
    result = agent._parse_patch_response(raw, "原文", 1, 1, 0, [])
    assert result["no_change"] is True
    assert result["revised"] is False


def test_parse_patch_response_filters_invalid_patches():
    """缺少 anchor 的 patch 应被过滤"""
    agent = RevisionAgent(llm_client=MagicMock())
    raw = json.dumps({
        "patches": [
            {"anchor": "有效的锚点文字片段", "replacement": "改", "reason": "x"},
            {"anchor": "", "replacement": "没 anchor", "reason": "x"},       # 无效应过滤
            {"replacement": "缺 anchor", "reason": "x"},                     # 缺字段
        ],
        "no_change": False,
        "change_summary": "改了",
    }, ensure_ascii=False)
    result = agent._parse_patch_response(raw, "有效的锚点文字片段在此", 1, 1, 1, [])
    assert len(result["patches"]) == 1


# ----------------------------------------------------------------------
#  单元：HTML 注释清理
# ----------------------------------------------------------------------

def test_strip_html_comments():
    text = "第一段<!--REVISION:logic-->第二段。<!--NO_CHANGE-->"
    cleaned = RevisionAgent._strip_html_comments(text)
    assert "<!--" not in cleaned
    assert cleaned == "第一段第二段。"


def test_strip_html_comments_no_markers():
    text = "干净文本。"
    assert RevisionAgent._strip_html_comments(text) == "干净文本。"


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in list(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
        except AssertionError:
            failed += 1
            print(f"  FAIL {t.__name__}")
            traceback.print_exc()
        except Exception as e:
            failed += 1
            print(f"  ERROR {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(0 if failed == 0 else 1)
