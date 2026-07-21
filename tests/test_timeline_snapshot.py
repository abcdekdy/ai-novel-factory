"""
时间线快照（G2）集成测试
- 多章节、多角色的 timeline/character_states/unresolved_threads 正确构建
- save/load 落盘往返
"""
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
QApplication.instance() or QApplication(sys.argv)

from core import project_manager as pm  # noqa: E402
from core.pipeline import NovelPipeline  # noqa: E402


def _make_project(tmp: Path, *, with_world=True, chapters=2,
                  with_outline=True):
    if with_world:
        (tmp / "world_view.json").write_text(json.dumps({
            "title": "测试",
            "characters": [
                {"name": "林凡", "desc": "孤儿", "role": "主角",
                 "ability": "剑意"},
                {"name": "苏婉儿", "desc": "宗主之女", "role": "女主",
                 "ability": "琴音"},
            ]}, ensure_ascii=False), encoding="utf-8")

    ch_dir = tmp / "chapters"
    ch_dir.mkdir(exist_ok=True)
    for i in range(1, chapters + 1):
        chars = ["林凡"] if i == 1 else ["林凡", "苏婉儿"]
        (ch_dir / f"chapter_{i:03d}_meta.json").write_text(json.dumps({
            "chapter_index": i,
            "title": f"第{i}章",
            "summary": f"第{i}章剧情摘要",
            "key_events": [f"事件{i}a", f"事件{i}b"],
            "characters_present": chars,
            "cliffhanger": f"第{i}章悬念",
        }, ensure_ascii=False), encoding="utf-8")

    if with_outline:
        (tmp / "outline.json").write_text(json.dumps({
            "chapters": [
                {"chapter_index": i, "title": f"第{i}章",
                 "foreshadowing": [f"伏笔{i}"]}
                for i in range(1, chapters + 1)
            ],
            "consistency_rules": ["规则1"],
            "character_arcs": {
                "林凡": {
                    "arc_type": "成长型",
                    "trajectory": [
                        {"chapter": 1, "state": "入门"},
                        {"chapter": chapters, "state": "金丹初期"},
                    ],
                },
            },
        }, ensure_ascii=False), encoding="utf-8")


def test_timeline_basic():
    tmp = Path(tempfile.mkdtemp())
    _make_project(tmp, chapters=3)
    snap = pm.build_timeline_snapshot(tmp)
    assert snap["total_chapters"] == 3
    assert len(snap["timeline"]) == 3
    assert "林凡" in snap["character_states"]
    assert "苏婉儿" in snap["character_states"]
    # 林凡出现在全部 3 章
    assert snap["character_states"]["林凡"]["appearance_chapters"] == [1, 2, 3]
    # 苏婉儿从第 2 章出场
    assert snap["character_states"]["苏婉儿"]["first_appearance"] == 2


def test_timeline_character_first_last():
    tmp = Path(tempfile.mkdtemp())
    _make_project(tmp, chapters=4)
    snap = pm.build_timeline_snapshot(tmp)
    lf = snap["character_states"]["林凡"]
    assert lf["first_appearance"] == 1
    assert lf["last_appearance"] == 4
    assert lf["latest_state"] == "金丹初期"   # 来自 arcs


def test_timeline_unresolved_foreshadowing():
    tmp = Path(tempfile.mkdtemp())
    _make_project(tmp, chapters=2)
    snap = pm.build_timeline_snapshot(tmp)
    # outline 中每个 chapter 留一个 foreshadowing
    assert len(snap["unresolved_threads"]) >= 2
    types = {t["type"] for t in snap["unresolved_threads"]}
    assert "foreshadowing" in types


def test_save_load_roundtrip():
    tmp = Path(tempfile.mkdtemp())
    _make_project(tmp, chapters=2)
    snap = pm.build_timeline_snapshot(tmp)
    saved_path = pm.save_timeline_snapshot(tmp, snap)
    assert saved_path.exists()
    loaded = pm.load_timeline_snapshot(tmp)
    assert loaded["total_chapters"] == 2
    assert loaded["generated_at"] == snap["generated_at"]


def test_empty_project_returns_safe_default():
    tmp = Path(tempfile.mkdtemp())
    # 无任何文件
    snap = pm.build_timeline_snapshot(tmp)
    assert snap["total_chapters"] == 0
    assert snap["timeline"] == []
    assert snap["character_states"] == {}
    assert snap["unresolved_threads"] == []


def test_legacy_package_includes_timeline():
    tmp = Path(tempfile.mkdtemp())
    _make_project(tmp, chapters=2)
    legacy = pm.load_legacy_package(tmp)
    assert "timeline_snapshot" in legacy
    snap = legacy["timeline_snapshot"]
    assert snap["total_chapters"] == 2
    assert "林凡" in snap["character_states"]


def test_pipeline_saves_snapshot_on_finish():
    """流水线完成时 timeline_snapshot.json 应被写到项目目录。"""
    tmp = Path(tempfile.mkdtemp())
    _make_project(tmp, chapters=2)

    p = NovelPipeline()
    p.initialize(api_key="test-key")
    p.llm = MagicMock()
    p.is_running = True
    p.project_dir = tmp
    p.world_view = {"title": "测试", "characters": [
        {"name": "林凡", "desc": "", "role": "", "ability": ""}]}
    p._chapter_length = 3000
    p.chapters = [
        {"chapter_index": 1, "word_count": 100, "title": "第1章"},
        {"chapter_index": 2, "word_count": 100, "title": "第2章"},
    ]
    p.evaluations = {}

    # 直接调 _finish_pipeline（同步走完）
    p._finish_pipeline()

    snap_path = tmp / "timeline_snapshot.json"
    assert snap_path.exists(), "流水线完成时应落盘 timeline_snapshot.json"
    loaded = json.loads(snap_path.read_text(encoding="utf-8"))
    assert loaded["total_chapters"] == 2

    p.stop()


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
