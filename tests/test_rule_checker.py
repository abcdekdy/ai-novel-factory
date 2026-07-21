"""
rule_checker 冒烟 + 单元测试
运行：python -m pytest tests/test_rule_checker.py -v
"""

import sys
from pathlib import Path

# 让 core 包从上级目录可导入（避免在项目外跑测试报错）
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.rule_checker import check_chapter, truncate  # noqa: E402


# ----------------------------------------------------------------------
#  工具
# ----------------------------------------------------------------------

def _ctx(**over) -> dict:
    base = {
        "chapter_index": 1,
        "target_length": 1000,
        "key_events": [],
        "foreshadowing": [],
        "cliffhanger": "",
        "characters_present": [],
        "characters_all": ["林凡", "苏婉儿", "掌门"],
        "consistency_rules": [],
        "world_rules": "",
    }
    base.update(over)
    return base


def _gen_text(chars: int, ending: str = "。") -> str:
    """生成指定字数的占位中文文本，尾字为 ending。"""
    body = "天地灵气充盈于山林之间修士打坐吐纳。" * (chars // 16 + 1)
    body = body[:chars - len(ending)]
    return body + ending


# ----------------------------------------------------------------------
#  1. 字数
# ----------------------------------------------------------------------

def test_word_count_pass():
    content = _gen_text(1000)
    r = check_chapter(content, _ctx(target_length=1000))
    assert r["rule_pass"] is True
    assert r["stats"]["word_count"]["pass"] is True


def test_word_count_hard_fail_too_short():
    content = _gen_text(500)   # 少 50%
    r = check_chapter(content, _ctx(target_length=1000))
    assert r["rule_pass"] is False
    assert r["stats"]["word_count"]["pass"] is False
    assert any(i["type"] == "word_count" and i["severity"] == "hard"
               for i in r["hard_issues"])


def test_word_count_soft_warn():
    content = _gen_text(820)   # 少 18% → soft
    r = check_chapter(content, _ctx(target_length=1000))
    assert r["rule_pass"] is True          # soft 不卡流程
    assert any(i["type"] == "word_count" for i in r["soft_issues"])


# ----------------------------------------------------------------------
#  2. 禁用句式
# ----------------------------------------------------------------------

def test_forbidden_chapter_marker():
    content = _gen_text(1000)
    # 在中间塞一个章标题标记
    content = content[:500] + "第一章 风起" + content[500:]
    r = check_chapter(content, _ctx(target_length=1000))
    assert r["stats"]["forbidden"]["pass"] is False
    assert any(i["type"] == "forbidden_phrase" for i in r["hard_issues"])


def test_forbidden_benzhangshuo():
    content = "本章说：" + _gen_text(1000)
    r = check_chapter(content, _ctx(target_length=len(content)))
    assert any("本章说" in i["description"] for i in r["hard_issues"])


def test_english_paragraph_soft():
    english_para = "He opened his eyes and realized the world had changed completely overnight. "
    content = _gen_text(1000) + "\n\n" + english_para + "\n\n" + _gen_text(200)
    r = check_chapter(content, _ctx(target_length=len(content)))
    soft_types = [i["type"] for i in r["soft_issues"]]
    assert "forbidden_phrase" in soft_types


def test_clean_chinese_no_forbidden():
    content = _gen_text(1000)
    r = check_chapter(content, _ctx(target_length=1000))
    assert r["stats"]["forbidden"]["pass"] is True


# ----------------------------------------------------------------------
#  3. 章尾钩子
# ----------------------------------------------------------------------

def test_cliffhanger_ok_question():
    content = _gen_text(1000, ending="？")
    r = check_chapter(content, _ctx(target_length=len(content)))
    assert r["stats"]["cliffhanger"]["hook_detected"] is True


def test_cliffhanger_ok_opener():
    content = _gen_text(900) + "谁也没想到，这一去竟是永别。"
    r = check_chapter(content, _ctx(target_length=len(content)))
    assert r["stats"]["cliffhanger"]["hook_detected"] is True


def test_cliffhanger_weak_plain_end():
    content = _gen_text(1000, ending="。")
    r = check_chapter(content, _ctx(target_length=len(content)))
    # 普通结尾只 soft 不卡流程
    assert r["rule_pass"] is True
    assert any(i["type"] == "cliffhanger" for i in r["soft_issues"])


# ----------------------------------------------------------------------
#  4. 关键事件覆盖
# ----------------------------------------------------------------------

def test_key_events_all_covered():
    content = "林凡在思过崖上修炼，忽然感应到苏婉儿的灵力波动。"
    content += _gen_text(500)
    r = check_chapter(content, _ctx(
        target_length=len(content),
        key_events=["林凡在思过崖修炼", "苏婉儿感应到危机"],
    ))
    assert r["stats"]["key_events"]["total"] == 2
    assert r["stats"]["key_events"]["covered"] == 2


def test_key_events_missing_flagged():
    content = "林凡独自一人在崖边打坐，未察觉身后动静。" + _gen_text(500)
    r = check_chapter(content, _ctx(
        target_length=len(content),
        key_events=["林凡在思过崖修炼", "苏婉儿前来探望"],
    ))
    # "苏婉儿" 不在内容内 → missing
    assert "苏婉儿前来探望" in r["stats"]["key_events"]["missing"]
    assert any(i["type"] == "key_event_missing" for i in r["soft_issues"])


# ----------------------------------------------------------------------
#  5. 出场人物
# ----------------------------------------------------------------------

def test_characters_all_present():
    content = "林凡看着苏婉儿离去，心中五味杂陈。" + _gen_text(500)
    r = check_chapter(content, _ctx(
        target_length=len(content),
        characters_present=["林凡", "苏婉儿"],
    ))
    assert r["stats"]["characters"]["pass"] is True
    assert r["stats"]["characters"]["missing"] == []


def test_characters_one_missing():
    content = "林凡独自走在山路上，心中想着旧事。" + _gen_text(500)
    r = check_chapter(content, _ctx(
        target_length=len(content),
        characters_present=["林凡", "苏婉儿"],
    ))
    assert "苏婉儿" in r["stats"]["characters"]["missing"]
    assert any(i["type"] == "character_missing" for i in r["soft_issues"])


# ----------------------------------------------------------------------
#  综合（典型满章）
# ----------------------------------------------------------------------

def test_full_typical_chapter_passes():
    """模拟一个合格章：字数在目标区间、无禁用、带钩子、覆盖事件、出场人物齐全。"""
    content = "林凡回到洞府，发现苏婉儿留下的书信。他展开细读，得知她已悄然离去。"
    content += _gen_text(900)
    content += "谁也没想到，她此去竟是赴死之旅，而他还被蒙在鼓里。"
    r = check_chapter(content, _ctx(
        target_length=1000,
        key_events=["林凡读到书信", "苏婉儿离去"],
        characters_present=["林凡", "苏婉儿"],
        cliffhanger="苏婉儿赴死",
    ))
    assert r["rule_pass"] is True
    assert r["stats"]["word_count"]["pass"] is True
    assert r["stats"]["forbidden"]["pass"] is True
    assert r["stats"]["cliffhanger"]["hook_detected"] is True
    assert r["stats"]["key_events"]["covered"] == 2
    assert r["stats"]["characters"]["missing"] == []


def test_truncate_helper():
    assert truncate("abcdef", 4) == "abcd…"
    assert truncate("abc", 10) == "abc"
    assert truncate(None, 5) == ""


if __name__ == "__main__":
    # 直接运行脚本也支持简易输出
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
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
