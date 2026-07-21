"""
世界观审查检查点测试 —— 直接调用内部方法，避免跨线程 signal 时序。
验证：_build_world_view 完成后流水线暂停、confirm_world_view 继续、
      discard_world_view 中止。
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# signal-slot 需要 QApplication
from PyQt6.QtWidgets import QApplication
QApplication.instance() or QApplication(sys.argv)

from core.pipeline import NovelPipeline  # noqa: E402


def _world_view_result():
    return {
        "title": "测试世界",
        "genre": "玄幻",
        "summary": "这是一个测试用的世界观简介。" * 20,
        "world_view": {
            "era": "上古", "location": "东胜神洲",
            "rules": "灵气不能逆练",
            "factions": ["天剑宗", "幽冥教"],
            "history": "万年前大战",
        },
        "characters": [
            {"name": "林凡", "role": "主角", "desc": "孤儿", "ability": "剑意"},
            {"name": "苏婉儿", "role": "女主", "desc": "宗主之女", "ability": "琴音"},
        ],
        "story_framework": {
            "premise": "复仇", "conflict": "灭门",
            "climax": "决战", "ending_type": "开放式",
        },
        "chapter_outline": [
            {"chapter": 1, "title": "第一章", "summary": "开篇"},
            {"chapter": 2, "title": "第二章", "summary": "发展"},
        ],
    }


def _build_prepared_pipeline():
    """构造 pipeline 状态（跳过 start() 的线程启动），手动调用 _build_world_view。"""
    p = NovelPipeline()
    p.initialize(api_key="test-key")
    p.llm = MagicMock()
    # 模拟 start() 里的初始化参数
    p.is_running = True
    p._pause_requested = False
    p.chapters = []
    p.evaluations = {}
    p.adaptations = {}
    p._chapter_count = 2
    p._chapter_length = 3000
    p._completed_chapters = 0
    import core.project_manager as pm
    # 用内存保存替代落盘
    p._save_world_view_stub = MagicMock()
    p._save_summary_stub = MagicMock()
    return p


def test_world_view_review_pauses_pipeline():
    """_build_world_view 应让流水线进入 _world_view_reviewing 暂停状态。"""
    p = _build_prepared_pipeline()
    mock_agent = MagicMock()
    mock_agent.run.return_value = _world_view_result()
    # log_signal.connect 被调用时不要报错
    mock_agent.log_signal = MagicMock()
    mock_agent.progress_signal = MagicMock()

    from core import pipeline as pipeline_mod
    orig_save_wv = pipeline_mod.save_world_view
    orig_save_summary = pipeline_mod.save_project_summary
    pipeline_mod.save_world_view = MagicMock()
    pipeline_mod.save_project_summary = MagicMock()
    try:
        with patch.object(pipeline_mod, "WorldBuilderAgent",
                          return_value=mock_agent):
            p._build_world_view("测试灵感", chapter_count=2)

        assert p._world_view_reviewing is True, \
            "世界观构建完后应进入 _world_view_reviewing 状态"
        assert p.is_running is True, "审查期间流水线仍标记为 running"
        assert p.world_view["title"] == "测试世界"
        assert p._pending_world_view is not None
        # current_stage 仍留在 world_building（用户确认后才走）
        assert p.current_stage == "world_building"
    finally:
        pipeline_mod.save_world_view = orig_save_wv
        pipeline_mod.save_project_summary = orig_save_summary
        p.stop()


def test_confirm_world_view_resumes_to_outline():
    """confirm_world_view 后流水线应进入 outline_generation。"""
    p = _build_prepared_pipeline()
    mock_agent = MagicMock()
    mock_agent.run.return_value = _world_view_result()
    mock_agent.log_signal = MagicMock()
    mock_agent.progress_signal = MagicMock()

    from core import pipeline as pipeline_mod
    pipeline_mod.save_world_view = MagicMock()
    pipeline_mod.save_project_summary = MagicMock()
    try:
        with patch.object(pipeline_mod, "WorldBuilderAgent",
                          return_value=mock_agent):
            p._build_world_view("测试灵感", chapter_count=2)

        # 确认处于审查状态
        assert p._world_view_reviewing is True

        # 模拟审阅后确认（改书名 + 加角色）
        reviewed = _world_view_result()
        reviewed["title"] = "审阅后书名"
        reviewed["characters"].append(
            {"name": "新角色", "role": "师弟", "desc": "", "ability": ""})

        mock_outline = MagicMock()
        mock_outline.run.return_value = {"chapters": []}
        mock_outline.log_signal = MagicMock()
        mock_outline.progress_signal = MagicMock()
        with patch.object(pipeline_mod, "OutlineBuilderAgent",
                          return_value=mock_outline):
            p.confirm_world_view(reviewed)

        assert p.world_view["title"] == "审阅后书名"
        assert p._world_view_reviewing is False
        # _build_outline 开新线程，等最多 0.5 秒让线程把 stage 改掉
        # （mock outline 返回空 chapters，流水线会一口气跑完 outline → chapter）
        deadline = time.time() + 0.5
        while time.time() < deadline and p.current_stage == "world_building":
            time.sleep(0.02)
        assert p.current_stage != "world_building", \
            f"确认后应离开 world_building 阶段，实际={p.current_stage}"
    finally:
        p.stop()


def test_discard_world_view_stops_pipeline():
    """discard_world_view 后流水线应停止。"""
    p = _build_prepared_pipeline()
    mock_agent = MagicMock()
    mock_agent.run.return_value = _world_view_result()
    mock_agent.log_signal = MagicMock()
    mock_agent.progress_signal = MagicMock()

    from core import pipeline as pipeline_mod
    pipeline_mod.save_world_view = MagicMock()
    pipeline_mod.save_project_summary = MagicMock()
    try:
        with patch.object(pipeline_mod, "WorldBuilderAgent",
                          return_value=mock_agent):
            p._build_world_view("测试灵感", chapter_count=2)

        p.discard_world_view()
        assert p.is_running is False
        assert p.current_stage == "idle"
        assert p._world_view_reviewing is False
        assert p.world_view is None
    finally:
        p.stop()


def test_worldview_review_dialog_confirm_roundtrip():
    """WorldViewReviewDialog._deep_copy + 字段回写正确工作（无 GUI）。"""
    from gui.worldview_review_dialog import WorldViewReviewDialog
    wv = _world_view_result()
    copied = WorldViewReviewDialog._deep_copy(wv)
    copied["title"] = "新书名"
    copied["world_view"]["rules"] = "新规则"
    copied["characters"][0]["name"] = "新名字"
    assert wv["title"] == "测试世界"
    assert wv["characters"][0]["name"] == "林凡"
    assert copied["title"] == "新书名"
    assert copied["world_view"]["rules"] == "新规则"
    assert copied["characters"][0]["name"] == "新名字"


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
