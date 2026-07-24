"""
流水线编排引擎
串联各Agent完成任务，管理并发、修订循环、状态广播

工作流程：
灵感 → 世界观构建 → 并行章节生成 → 质量评估 → 修订循环 → 多平台适配 → 完成
"""

import time
import json
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from core.llm_client import LLMClient
from core.config import load_config
from core.world_agent import WorldBuilderAgent
from core.outline_agent import OutlineBuilderAgent
from core.continuation_outline_agent import ContinuationOutlineAgent
from core.chapter_agent import ChapterGeneratorAgent
from core.quality_agent import QualityEvaluatorAgent
from core.revision_agent import RevisionAgent
from core.adapter_agent import PlatformAdapterAgent
from core.project_manager import (
    create_project, save_world_view, save_chapter,
    save_project_summary, load_project_summary,
    export_to_txt, export_to_markdown,
    load_world_view, load_outline,
    load_all_chapters_map, load_legacy_package,
    save_batch_outline, load_batch_outline,
    list_batch_outlines, get_next_batch_number,
    load_all_chapters, update_project_batches,
    build_timeline_snapshot, save_timeline_snapshot,
)


class PipelineSignals(QObject):
    """流水线全局信号"""
    # 阶段信号
    stage_started = pyqtSignal(str)        # 阶段名称
    stage_completed = pyqtSignal(str)      # 阶段名称
    stage_error = pyqtSignal(str, str)     # (阶段名称, 错误信息)

    # 进度信号
    overall_progress = pyqtSignal(int)     # 整体进度 0-100
    chapter_progress = pyqtSignal(int, int, str)  # (章索引, 进度, 状态)

    # 结果信号
    world_view_ready = pyqtSignal(dict)    # 世界观准备好
    outline_ready = pyqtSignal(dict)       # 详细大纲准备好
    chapter_ready = pyqtSignal(dict)       # 单个章节完成
    evaluation_ready = pyqtSignal(dict)    # 评估完成
    revision_ready = pyqtSignal(dict)      # 修订完成
    adaptation_ready = pyqtSignal(dict)    # 适配完成
    pipeline_finished = pyqtSignal(dict)  # 流水线完成（含全部结果）
    # ---- 续写专用信号 ----
    continuation_outline_ready = pyqtSignal(dict)   # 续写大纲已生成，待用户审阅
    continuation_progress = pyqtSignal(str, int)    # (阶段文本, 进度0-100)

    # ---- 世界观审查信号 ----
    world_view_review_ready = pyqtSignal(dict)      # 世界观已生成，待用户审阅

    # 日志
    log_signal = pyqtSignal(str, str)      # (source, message)

    # Token统计
    token_update = pyqtSignal(str, int)    # (agent_name, tokens_used)


class NovelPipeline(QObject):
    """小说生成流水线引擎"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = PipelineSignals()
        self.config = load_config()
        self.llm = None
        self.project_dir = None
        self.world_view = None
        self.outline = None          # 详细大纲（OutlineBuilderAgent 产出）
        self.chapters = []
        self.evaluations = {}
        self.adaptations = {}

        # 流水线状态
        self.is_running = False
        self.current_stage = ""
        self._chapter_count = 0
        self._completed_chapters = 0
        self._pause_requested = False
        self._pending_chapter_workers = 0

        # 修订循环状态
        self._revision_queue = []
        self._revision_in_progress = False

        # ---- 续写状态 ----
        self._continuation_outline = None     # 待审阅的续写大纲
        self._continuation_guidance = ""       # 用户给的本批续写指引
        self._continuation_batch = 0          # 本批批次号
        self._continuation_legacy = None      # 遗产包缓存

        self._outline_for_chapters = None     # 当前用于章节生成的大纲（可能是续写批次的）

    def initialize(self, api_key: str = None):
        """初始化LLM客户端"""
        if api_key is None:
            api_key = self.config.get("api_key", "")
        self.llm = LLMClient(
            api_key=api_key,
            provider=self.config.get("provider", "longcat"),
            base_url=self.config.get("base_url"),
            model=self.config.get("model", "LongCat-2.0")
        )
        self.signals.log_signal.emit(
            "Pipeline",
            f"LLM客户端初始化完成 | Provider: {self.llm.provider} | 模型: {self.llm.model}"
        )

    def start(self, inspiration: str, chapter_count: int = None, chapter_length: int = None):
        """
        启动完整流水线
        """
        if self.is_running:
            self.signals.log_signal.emit("Pipeline", "⚠️ 流水线已在运行中")
            return

        if not self.llm:
            self.initialize()

        # 参数准备
        if chapter_count is None:
            chapter_count = self.config.get("default_chapter_count", 5)
        if chapter_length is None:
            chapter_length = self.config.get("default_chapter_length", 3000)

        self.is_running = True
        self._pause_requested = False
        self.chapters = []
        self.evaluations = {}
        self.adaptations = {}
        self._chapter_count = chapter_count
        self._chapter_length = chapter_length  # 保存供后续阶段使用
        self._completed_chapters = 0
        self._chapter_results = {}
        self._chapter_completed_count = 0
        self._pending_chapter_workers = 0

        # 创建项目目录
        safe_name = inspiration[:20] if inspiration else "untitled"
        self.project_dir = create_project(safe_name)

        self.signals.log_signal.emit("Pipeline", f"🚀 流水线启动 | 灵感: {inspiration[:30]}... | {chapter_count}章")
        self.signals.overall_progress.emit(0)

        # 在后台线程运行流水线（避免阻塞GUI）
        # 所有通过信号触发的阶段切换都在主线程执行（Qt信号跨线程安全）
        import threading

        def run_pipeline():
            try:
                self._build_world_view(inspiration, chapter_count)
            except Exception as e:
                self.signals.log_signal.emit("Pipeline", f"❌ 流水线异常: {e}")

        self._pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
        self._pipeline_thread.start()

    def _build_world_view(self, inspiration: str, chapter_count: int):
        """Step 1: 构建世界观"""
        self.current_stage = "world_building"
        self.signals.stage_started.emit("世界观构建")
        self.signals.log_signal.emit("Pipeline", "📖 [1/5] 世界观构建Agent 启动...")

        agent = WorldBuilderAgent(self.llm)

        # 连接信号以转发
        agent.log_signal.connect(lambda name, msg: self.signals.log_signal.emit(name, msg))
        agent.progress_signal.connect(lambda name, pct: (
            self.signals.overall_progress.emit(int(pct * 0.15)),  # 世界观占15%
            self.signals.chapter_progress.emit(0, pct, "世界观构建中")
        ))

        try:
            result = agent.run({
                "inspiration": inspiration,
                "chapter_count": chapter_count
            })

            if "error" in result:
                if self._finalize_pause_if_requested():
                    return
                self.signals.stage_error.emit("世界观构建", result["error"])
                self._handle_error(f"世界观构建失败: {result['error']}")
                return

            self.world_view = result

            # 保存世界观
            if self.project_dir:
                save_world_view(self.project_dir, result)
                save_project_summary(self.project_dir, {
                    "inspiration": inspiration,
                    "title": result.get("title", ""),
                    "chapter_count": chapter_count,
                    "chapter_length": self._chapter_length,
                    "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "generating"
                })

            # ---- 世界观审查检查点：暂停流水线，等用户审阅 ----
            self._pending_world_view = result
            self._world_view_reviewing = True
            self.signals.world_view_ready.emit(result)
            self.signals.stage_completed.emit("世界观构建")
            self.signals.log_signal.emit(
                "Pipeline",
                f"✅ 世界观构建完成: {result.get('title', '')} — 等待用户审阅")
            self.signals.world_view_review_ready.emit(result)
            # 注意：不调用 _build_outline；等用户在 main_window 里调
            # confirm_world_view() / discard_world_view() 后再继续。

        except Exception as e:
            self.signals.stage_error.emit("世界观构建", str(e))
            self._handle_error(f"世界观构建异常: {e}")

    def _build_outline(self, world_view: dict, resume_existing: dict = None):
        """Step 1.5: 根据世界观生成详细大纲（消除章节间矛盾）"""
        self.current_stage = "outline_generation"
        self.signals.stage_started.emit("大纲生成")
        self.signals.log_signal.emit("Pipeline", "📋 [1.5] 大纲生成Agent 启动...")

        agent = OutlineBuilderAgent(
            self.llm,
            temperature=self.config.get("outline_temperature", 0.7),
            max_tokens=self.config.get("outline_max_tokens", 8192),
        )
        agent.log_signal.connect(lambda name, msg: self.signals.log_signal.emit(name, msg))
        agent.progress_signal.connect(lambda name, pct: (
            self.signals.overall_progress.emit(10 + int(pct * 0.15)),  # 大纲占 10%-25%
            self.signals.chapter_progress.emit(0, int(pct * 0.15), "生成详细大纲")
        ))

        try:
            result = agent.run({"world_view": world_view})

            if "error" in result and not result.get("chapters"):
                if self._finalize_pause_if_requested():
                    return
                self.signals.stage_error.emit("大纲生成", result["error"])
                self._handle_error(f"大纲生成失败: {result['error']}")
                return

            self.outline = result

            # 保存大纲到项目目录
            if self.project_dir:
                import json
                from pathlib import Path
                outline_path = Path(self.project_dir) / "outline.json"
                outline_path.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )

            self.signals.outline_ready.emit(result)
            self.signals.stage_completed.emit("大纲生成")
            rules = len(result.get("consistency_rules", []))
            arcs = len(result.get("character_arcs", {}))
            ch_count = len(result.get("chapters", []))
            self.signals.log_signal.emit(
                "Pipeline",
                f"✅ 大纲生成完成：{ch_count} 章详细大纲，{rules} 条一致性规则，{arcs} 条角色弧线"
            )

            # 进入下一步：新任务生成全部章节；恢复任务仅补缺失章节。
            if self._finalize_pause_if_requested():
                return
            if resume_existing is None:
                self._generate_chapters(self._chapter_length)
            else:
                self._resume_chapter_generation(resume_existing)

        except Exception as e:
            self.signals.stage_error.emit("大纲生成", str(e))
            self._handle_error(f"大纲生成异常: {e}")

    @staticmethod
    def _get_chapter_index(chapter: dict, fallback: int = None):
        """读取并标准化章节序号，兼容模型返回的数字字符串。"""
        if not isinstance(chapter, dict):
            return fallback
        value = chapter.get("chapter_index", chapter.get("chapter", fallback))
        try:
            return int(value)
        except (TypeError, ValueError):
            return value if value is not None else fallback

    def _outline_is_complete(self, outline: dict, coarse_outline: list) -> bool:
        """确认详细大纲覆盖所有章节，且每章包含可用的剧情细纲。"""
        if not isinstance(outline, dict) or not isinstance(coarse_outline, list):
            return False
        detailed_chapters = outline.get("chapters")
        if not isinstance(detailed_chapters, list):
            return False

        expected = {
            self._get_chapter_index(chapter, position)
            for position, chapter in enumerate(coarse_outline, start=1)
            if isinstance(chapter, dict)
        }
        detailed = {
            self._get_chapter_index(chapter, position)
            for position, chapter in enumerate(detailed_chapters, start=1)
            if isinstance(chapter, dict)
            and str(chapter.get("plot_detail", "")).strip()
        }
        return bool(expected) and expected.issubset(detailed)

    def _resume_chapter_generation(self, existing: dict):
        """从已保存的大纲继续，只生成尚未落盘的章节。"""
        self.signals.log_signal.emit(
            "Pipeline", f"▶️ _resume_chapter_generation 启动，"
                        f"world_view={'有' if self.world_view else '无'}, "
                        f"outline={'有' if self.outline else '无'}, "
                        f"existing={len(existing)} 章")
        coarse_outline = self.world_view.get("chapter_outline", [])
        total_needed = len(coarse_outline)
        outline_chapters = self.outline.get("chapters", []) if self.outline else []
        outline_detail_map = {
            self._get_chapter_index(chapter, position): chapter
            for position, chapter in enumerate(outline_chapters, start=1)
            if isinstance(chapter, dict)
        }

        existing = {
            self._get_chapter_index(chapter, index): chapter
            for index, chapter in existing.items()
            if isinstance(chapter, dict)
        }
        missing = [
            self._get_chapter_index(chapter, position)
            for position, chapter in enumerate(coarse_outline, start=1)
            if self._get_chapter_index(chapter, position) not in existing
        ]

        self.chapters = [existing[index] for index in sorted(existing)]
        self._chapter_count = total_needed
        self._total_chapters = total_needed
        # _gen_chapter_worker / _on_chapter_complete 使用 0 基位置作为缓存键。
        self._chapter_results = {
            index - 1: chapter for index, chapter in existing.items()
            if isinstance(index, int)
        }
        self._chapter_completed_count = len(self._chapter_results)
        self._completed_chapters = self._chapter_completed_count
        self._pending_chapter_workers = len(missing)

        if not missing:
            self.signals.log_signal.emit(
                "Pipeline", f"✅ 项目全部 {total_needed} 章均已生成，继续后续处理")
            self._on_all_chapters_complete()
            return

        self.current_stage = "chapter_generation"
        self.signals.stage_started.emit("章节生成")
        self.signals.log_signal.emit(
            "Pipeline",
            f"▶️ 从章节断点继续：已完成 {len(existing)}/{total_needed} 章，"
            f"缺失: {missing}")

        import threading
        self._semaphore = threading.Semaphore(self.config.get("concurrency", 2))
        self._chapter_lock = threading.Lock()

        for position, outline_entry in enumerate(coarse_outline, start=1):
            chapter_index = self._get_chapter_index(outline_entry, position)
            if chapter_index not in missing:
                continue

            previous = existing.get(chapter_index - 1, {})
            outline_chapter = outline_detail_map.get(chapter_index, {})
            input_data = {
                "world_view": self.world_view,
                "chapter_outline": outline_entry,
                "chapter_index": chapter_index,
                "target_length": self._chapter_length,
                "previous_chapter_summary": previous.get("summary", ""),
                "outline_chapter": outline_chapter,
                "outline_context": self._build_outline_context(),
                "character_arcs": self.outline.get("character_arcs", {}),
            }
            threading.Thread(
                target=self._gen_chapter_worker,
                args=(chapter_index - 1, input_data),
                daemon=True,
            ).start()

    def _generate_chapters(self, chapter_length: int):
        """Step 2: 并行生成章节（携带详细大纲上下文）"""
        self.current_stage = "chapter_generation"
        self.signals.stage_started.emit("章节生成")
        self.signals.log_signal.emit("Pipeline", "✍️ [2/5] 章节并行生成启动...")

        outlines = self.world_view.get("chapter_outline", [])
        concurrency = self.config.get("concurrency", 3)
        self._total_chapters = len(outlines)

        self.signals.log_signal.emit(
            "Pipeline",
            f"并发数: {concurrency}，共 {self._total_chapters} 章"
        )

        # ---- 构建大纲上下文（供每章 agent 感知整体） ----
        outline_chapters = self.outline.get("chapters", []) if self.outline else []
        outline_detail_map = {ch.get("chapter_index"): ch for ch in outline_chapters}
        outline_context = self._build_outline_context()

        # 使用Python线程信号量控制并发（跨线程安全）
        import threading
        self._semaphore = threading.Semaphore(concurrency)
        self._chapter_results = {}
        self._chapter_completed_count = 0
        self._chapter_lock = threading.Lock()
        self._pending_chapter_workers = len(outlines)
        self._chapter_length = chapter_length  # 保存供后续引用

        # 为每个章节创建独立线程来生成（不用QThreadPool，避免线程池嵌套问题）
        for i, outline in enumerate(outlines):
            chapter_index = outline.get("chapter_index", i + 1)
            # 获取前情提要
            prev_summary = ""
            if i > 0 and (i - 1) in self._chapter_results:
                prev_summary = self._chapter_results[i - 1].get("summary", "")

            # 本章节的详细大纲条目
            outline_ch = outline_detail_map.get(chapter_index, {})

            input_data = {
                "world_view": self.world_view,
                "chapter_outline": outline,
                "chapter_index": chapter_index,
                "target_length": chapter_length,
                "previous_chapter_summary": prev_summary,
                # ---- 新增：大纲上下文 ----
                "outline_chapter": outline_ch,
                "outline_context": outline_context,
                "character_arcs": self.outline.get("character_arcs", {}) if self.outline else {}
            }

            # 启动独立线程，由信号量控制并发数
            t = threading.Thread(
                target=self._gen_chapter_worker,
                args=(i, input_data),
                daemon=True
            )
            t.start()

    def _get_consistency_rules(self) -> list:
        """读取当前生效的全局一致性规则（详细大纲 + 所有续写批次合并）。"""
        if self.outline:
            rules = self.outline.get("consistency_rules", [])
            if isinstance(rules, list) and rules:
                return list(rules)
        # 续写场景：从 outline_for_chapters 收集
        if hasattr(self, "_outline_for_chapters") and self._outline_for_chapters:
            rules = self._outline_for_chapters.get("consistency_rules", [])
            if isinstance(rules, list) and rules:
                return list(rules)
        return []

    def _build_outline_context(self) -> dict:
        """构建供章节 agent 使用的大纲上下文"""
        if not self.outline:
            return {"consistency_rules": [], "all_chapters_summary": []}

        rules = self.outline.get("consistency_rules", [])

        # 所有章节的标题 + 概要（让每章 agent 知道前后章节走向）
        all_summary = []
        for ch in self.outline.get("chapters", []):
            all_summary.append({
                "chapter_index": ch.get("chapter_index"),
                "title": ch.get("title", ""),
                "plot_detail": ch.get("plot_detail", ""),
                "foreshadowing": ch.get("foreshadowing", [])
            })

        return {
            "consistency_rules": rules,
            "global_arc": self.outline.get("global_arc", {}),
            "all_chapters_summary": all_summary
        }

    def _gen_chapter_worker(self, idx: int, input_data: dict):
        """单章生成的工作函数（在线程中运行）"""
        # 获取信号量（控制并发数）
        self._semaphore.acquire()
        try:
            if self._pause_requested:
                return
            agent = ChapterGeneratorAgent(self.llm, agent_id=idx + 1)
            # 连接日志信号（Qt信号跨线程安全）
            agent.log_signal.connect(lambda name, msg: self.signals.log_signal.emit(name, msg))

            result = agent.run(input_data)
            self._on_chapter_complete(result, idx)
        except Exception as e:
            error_result = {
                "chapter_index": input_data.get("chapter_index", idx + 1),
                "content": f"[生成异常: {e}]",
                "title": input_data.get("chapter_outline", {}).get("title", ""),
                "word_count": 0,
                "status": "error",
                "error": str(e)
            }
            self._on_chapter_complete(error_result, idx)
        finally:
            self._semaphore.release()
            with self._chapter_lock:
                self._pending_chapter_workers -= 1
                workers_left = self._pending_chapter_workers
            if self._pause_requested and workers_left == 0:
                self._finalize_pause_if_requested()

    def _on_chapter_complete(self, result: dict, idx: int):
        """单个章节生成完成的回调"""
        # 防御性修复：确保chapter_index存在（兼容chapter字段名）
        if not result.get("chapter_index"):
            result["chapter_index"] = result.get("chapter") or idx + 1

        # 线程安全地更新完成计数
        with self._chapter_lock:
            self._chapter_results[idx] = result
            self._chapter_completed_count += 1
            completed = self._chapter_completed_count

        chapter_index = result.get("chapter_index")
        word_count = result.get("word_count", 0)

        self.signals.chapter_ready.emit(result)

        # 更新进度
        stage_progress = int((completed / self._total_chapters) * 100)
        overall = 25 + int(stage_progress * 0.35)  # 章节生成占35%（25%-60%）
        self.signals.overall_progress.emit(overall)
        self.signals.chapter_progress.emit(chapter_index, 100, "生成完成")

        self.signals.log_signal.emit(
            "Pipeline",
            f"📄 第{chapter_index}章完成 ({word_count}字) "
            f"[{completed}/{self._total_chapters}]"
        )

        # 保存章节
        if self.project_dir:
            save_chapter(self.project_dir, chapter_index, result)

        # 检查是否所有章节都完成了
        if not self._pause_requested and completed >= self._total_chapters:
            self._on_all_chapters_complete()

    def _on_all_chapters_complete(self):
        """所有章节生成完成，进入评估阶段"""
        # 续写场景：self.chapters 已预填旧章节，追加本批新章节
        if hasattr(self, "_continuation_new_indices") and self._continuation_new_indices:
            new_chapters = [self._chapter_results[i]
                            for i in sorted(self._chapter_results.keys())
                            if i >= len(self._chapter_results) - len(self._continuation_new_indices)]
            # 合并：旧章节（已有的）+ 新章节（刚生成的，用新内容替换占位）
            old_count = self._continuation_old_count
            self.chapters = self.chapters[:old_count] if old_count > 0 else []
            self.chapters.extend(new_chapters)
        else:
            # 通用流程：直接从 _chapter_results 排序
            self.chapters = [self._chapter_results[i]
                             for i in sorted(self._chapter_results.keys())]

        self.signals.stage_completed.emit("章节生成")
        self.signals.log_signal.emit(
            "Pipeline", f"✅ 全部 {len(self.chapters)} 章生成完成")
        self.signals.overall_progress.emit(60)

        # 进入下一步：质量评估（续写场景下只评估新章节）
        if hasattr(self, "_continuation_new_indices") and self._continuation_new_indices:
            self._evaluate_chapters(new_only=True)
        else:
            self._evaluate_chapters()

    def _evaluate_chapters(self, new_only: bool = False):
        """Step 3: 质量评估。
        new_only=True 时仅评估续写批次的新章节（self._continuation_new_indices）。
        """
        if self._finalize_pause_if_requested():
            return
        self.current_stage = "quality_evaluation"
        self.signals.stage_started.emit("质量评估")
        self.signals.log_signal.emit("Pipeline", "🔍 [3/5] 质量评估Agent 启动...")

        agent = QualityEvaluatorAgent(self.llm)
        agent.log_signal.connect(lambda name, msg: self.signals.log_signal.emit(name, msg))

        threshold = self.config.get("quality_threshold", 7.0)
        needs_revision = []
        passed = []

        # 构建详细大纲查找表（兼容续写场景：详细大纲在批次文件里）
        outline_detail_map = {}
        if hasattr(self, "_outline_for_chapters") and self._outline_for_chapters:
            for ch in self._outline_for_chapters.get("chapters", []):
                idx = ch.get("chapter_index")
                if idx is not None:
                    outline_detail_map[idx] = ch

        # 确定要评估的章节列表
        if new_only and hasattr(self, "_continuation_new_indices") and self._continuation_new_indices:
            eval_indices = [idx for idx in self._continuation_new_indices
                            if idx in outline_detail_map or True]
            chapters_to_eval = [c for c in self.chapters
                                if c.get("chapter_index") in self._continuation_new_indices]
        else:
            eval_indices = None
            chapters_to_eval = self.chapters

        total_to_eval = len(chapters_to_eval)
        self.signals.log_signal.emit(
            "Pipeline", f"评估范围: {total_to_eval} 章" + ("（仅新章节）" if new_only else ""))

        for i, chapter in enumerate(chapters_to_eval):
            if self._finalize_pause_if_requested():
                return
            chapter_index = chapter.get("chapter_index", i + 1)
            # 优先从详细大纲取，回退到粗大纲
            if chapter_index in outline_detail_map:
                chapter_outline = outline_detail_map[chapter_index]
            else:
                outline = self.world_view.get("chapter_outline", [])
                coarse_idx = chapter_index - 1
                chapter_outline = outline[coarse_idx] if coarse_idx < len(outline) else {}

            self.signals.log_signal.emit("Pipeline", f"评估中: 第{chapter_index}章...")

            try:
                evaluation = agent.run({
                    "content": chapter.get("content", ""),
                    "title": chapter.get("title", ""),
                    "chapter_index": chapter_index,
                    "world_view": self.world_view,
                    "chapter_outline": chapter_outline,
                    "summary": chapter.get("summary", ""),
                    # ---- 供 rule_checker 硬校验使用 ----
                    "target_length": self._chapter_length,
                    "consistency_rules": self._get_consistency_rules(),
                })

                self.evaluations[chapter_index] = evaluation
                self.signals.evaluation_ready.emit(evaluation)

                # 硬校验问题单独打印日志，便于作者快速定位
                hard_n = evaluation.get("rule_hard_count", 0)
                soft_n = evaluation.get("rule_soft_count", 0)
                if hard_n:
                    self.signals.log_signal.emit(
                        "Pipeline",
                        f"  ⚡ 第{chapter_index}章硬校验发现 {hard_n} 个严重问题"
                        + (f"，{soft_n} 个提醒" if soft_n else "")
                    )
                    for issue in evaluation.get("rule_issues", []):
                        if issue.get("severity") == "hard":
                            desc = issue.get("description", "")
                            self.signals.log_signal.emit(
                                "Pipeline", f"     ↳ [硬] {desc}"
                            )

                if evaluation.get("pass", False):
                    passed.append(chapter_index)
                    self.signals.chapter_progress.emit(chapter_index, 100, "评估通过")
                else:
                    needs_revision.append({
                        "chapter_index": chapter_index,
                        "evaluation": evaluation,
                        "round": 1
                    })
                    self.signals.chapter_progress.emit(chapter_index, 100, "需修订")

            except Exception as e:
                self.signals.log_signal.emit("Pipeline", f"⚠️ 第{chapter_index}章评估异常: {e}")
                needs_revision.append({
                    "chapter_index": chapter_index,
                    "evaluation": {"issues": [{"type": "system", "description": str(e), "suggestion": "重新评估"}], "pass": False},
                    "round": 1
                })

            # 更新进度
            stage_progress = int(((i + 1) / total_to_eval) * 100) if total_to_eval else 100
            overall = 60 + int(stage_progress * 0.15)  # 评估占15%（60%-75%）
            self.signals.overall_progress.emit(overall)

        if self._finalize_pause_if_requested():
            return

        self.signals.stage_completed.emit("质量评估")
        self.signals.log_signal.emit(
            "Pipeline",
            f"✅ 评估完成：通过 {len(passed)} 章，需修订 {len(needs_revision)} 章"
        )

        # 进入修订或直接到适配
        if needs_revision:
            self._revision_queue = needs_revision
            self._run_revisions()
        else:
            self._adapt_chapters()

    @staticmethod
    def _fuzzy_find(text: str, anchor: str) -> int:
        """
        在 text 里忽略空白与全半角标点差异地查找 anchor。
        返回锚点在 text 中的起始位置；未命中返回 -1。
        """
        import re

        def _normalize(s: str) -> str:
            s = re.sub(r"\s+", "", s)
            # 全角标点 → 半角
            full = "，。！？；：“”‘’（）【】《》"
            half = ",.!?;:\"\"''()[]<>"
            trans = str.maketrans(full, half)
            return s.translate(trans)

        norm_text = _normalize(text)
        norm_anchor = _normalize(anchor)
        if not norm_anchor:
            return -1
        idx = norm_text.find(norm_anchor)
        if idx == -1:
            return -1
        # 把 norm 里的位置映射回 text（跳过空白/标点差异）
        ti = 0
        for ni in range(len(norm_text)):
            if ti >= len(text):
                break
            if norm_text[ni] == _normalize(text[ti:ti + 1]):
                if ni == idx:
                    return ti
                ti += 1
        return -1

    @staticmethod
    def _apply_patches(content: str, patches: list, chapter_index: int) -> tuple:
        """
        把 patch 列表应用到 content 上。

        返回 (new_content, applied, failed, log_entries)：
          - new_content: 应用后的全文
          - applied: 成功替换的 patch 列表（含 reason）
          - failed: 未能命中的 anchor 列表
          - log_entries: 本轮改动摘要（供下一轮防震荡注入）
        """
        applied = []
        failed = []
        log_entries = []
        new_content = content

        for patch in patches:
            anchor = (patch.get("anchor") or "").strip()
            replacement = (patch.get("replacement") or "").strip()
            reason = patch.get("reason", "")
            if not anchor:
                failed.append(patch)
                continue

            # 1) 精确匹配
            pos = new_content.find(anchor)
            # 2) fuzzy 匹配
            if pos == -1:
                pos = NovelPipeline._fuzzy_find(new_content, anchor)
            if pos == -1:
                failed.append(patch)
                continue

            new_content = (new_content[:pos] + replacement
                           + new_content[pos + len(anchor):])
            applied.append(patch)
            log_entries.append({
                "reason": reason,
                "anchor": anchor[:40],
                "replacement_len": len(replacement),
            })

        return new_content, applied, failed, log_entries

    def _apply_revision_result(self, content: str, result: dict,
                               chapter_index: int, round_num: int) -> tuple:
        """
        根据 RevisionAgent 输出决定如何更新内容：
        - 模型标记 _fallback_full_rewrite → 直接替换全文（安全网）
        - 有 patch 且 >=50% 命中 → 局部替换
        - patch 命中 <50% → 回退到全文重写模式（再调一次模型）

        返回 (new_content, applied, failed, log_entries)。
        """
        # 安全网：模型已经返回全文
        if result.get("_fallback_full_rewrite"):
            self.signals.log_signal.emit(
                "Pipeline",
                f"第{chapter_index}章第{round_num}轮：模型回退到全文重写")
            new_content = result.get("_fallback_content", content)
            return new_content, [], [], []

        patches = result.get("patches", [])
        if not patches:
            # 模型说 no_change 或没输出 patch
            if result.get("no_change"):
                self.signals.log_signal.emit(
                    "Pipeline",
                    f"第{chapter_index}章第{round_num}轮：模型判断无需修改")
            return content, [], [], []

        new_content, applied, failed, log_entries = self._apply_patches(
            content, patches, chapter_index)

        total = len(patches)
        success_rate = len(applied) / total if total else 0

        self.signals.log_signal.emit(
            "Pipeline",
            f"第{chapter_index}章第{round_num}轮："
            f"{len(applied)}/{total} patch 命中"
            + (f"，{len(failed)} 失败" if failed else ""))

        # 太多 patch 失败 → 回退到全文重写模式（再调一次）
        if success_rate < 0.5 and total >= 2:
            self.signals.log_signal.emit(
                "Pipeline",
                f"⚠️ 第{chapter_index}章第{round_num}轮 patch 命中率过低"
                f"（{success_rate:.0%}），回退到全文重写")
            fallback_content = self._fallback_full_rewrite(
                content, result, chapter_index, round_num)
            return fallback_content, [], [], []

        return new_content, applied, failed, log_entries

    def _fallback_full_rewrite(self, content: str, result: dict,
                                chapter_index: int, round_num: int) -> str:
        """全文重写回退：直接用模型的 change_summary 拼一个简单修订提示，返回原文。

        这里选择"保留原文 + 标记"而不是再次调模型，是为了避免在修订失败后
        又消耗一次完整调用；用户可以在预览页手动修改后重新跑评估。
        """
        # 清理可能残留的 HTML 注释
        import re
        cleaned = re.sub(r"<!--REVISION:[^>]*?-->", "", content)
        cleaned = re.sub(r"<!--NO_CHANGE-->", "", cleaned).strip()
        self.signals.log_signal.emit(
            "Pipeline",
            f"第{chapter_index}章第{round_num}轮：全文重写回退，保留清理后的原文"
            "（建议手动修改后重跑评估）")
        return cleaned

    def _run_revisions(self):
        """Step 4: 修订循环"""
        if self._finalize_pause_if_requested():
            return
        if not self._revision_queue:
            self._adapt_chapters()
            return

        self.current_stage = "revision"
        self.signals.stage_started.emit("回流修订")
        self.signals.log_signal.emit("Pipeline", "🔄 [4/5] 回流修订Agent 启动...")

        max_rounds = self.config.get("max_revision_rounds", 3)
        next_round_queue = []

        for item in self._revision_queue:
            if self._finalize_pause_if_requested():
                return
            chapter_index = item["chapter_index"]
            evaluation = item["evaluation"]
            round_num = item["round"]

            # 找到原文
            chapter = next((c for c in self.chapters if c.get("chapter_index") == chapter_index), None)
            if not chapter:
                continue

            # 跳作者在预览页手动编辑过的章节（保护人的创作）
            if chapter.get("manually_edited"):
                self.signals.log_signal.emit(
                    "Pipeline",
                    f"第{chapter_index}章已标记为手动编辑，跳过修订以保留作者修改")
                continue

            self.signals.log_signal.emit(
                "Pipeline", f"修订第{chapter_index}章（第{round_num}轮）...")

            # 从 evaluation 里抽出 issues + highlights（E1 patch 协议）
            issues = evaluation.get("issues", [])
            highlights = evaluation.get("highlights", [])
            # 上一轮已生效的 patch（防震荡）
            previous_patches = chapter.get("revision_log", [])

            agent = RevisionAgent(self.llm)
            agent.log_signal.connect(
                lambda name, msg: self.signals.log_signal.emit(name, msg))

            try:
                result = agent.run({
                    "content": chapter.get("content", ""),
                    "issues": issues,
                    "highlights": highlights,
                    "world_view": self.world_view,
                    "chapter_index": chapter_index,
                    "current_round": round_num,
                    "max_rounds": max_rounds,
                    "previous_patches": previous_patches,
                })

                # ---- 应用 patch（或回退全文重写） ----
                revised_content, applied, failed, log_entries = \
                    self._apply_revision_result(chapter.get("content", ""),
                                                result, chapter_index,
                                                round_num)

                # 更新章节
                chapter["content"] = revised_content
                chapter["word_count"] = len(revised_content)
                chapter["revised"] = True
                chapter["revision_rounds"] = round_num
                # 累积修订 log（供下一轮防震荡）
                chapter.setdefault("revision_log", [])
                chapter["revision_log"].extend(log_entries)

                result["content"] = revised_content   # 兼容下游
                result["applied_count"] = len(applied)
                result["failed_count"] = len(failed)
                self.signals.revision_ready.emit(result)

                # 保存修订后的章节
                if self.project_dir:
                    save_chapter(self.project_dir, chapter_index, chapter)

                # 修订后再评估（含 rule_checker 重跑）
                if round_num < max_rounds and result.get("revised", False):
                    eval_agent = QualityEvaluatorAgent(self.llm)
                    outline = self.world_view.get("chapter_outline", [])
                    ch_idx = chapter_index - 1
                    chapter_outline = outline[ch_idx] if ch_idx < len(outline) else {}

                    new_eval = eval_agent.run({
                        "content": chapter["content"],
                        "title": chapter.get("title", ""),
                        "chapter_index": chapter_index,
                        "world_view": self.world_view,
                        "chapter_outline": chapter_outline,
                        "summary": chapter.get("summary", ""),
                        "target_length": self._chapter_length,
                        "consistency_rules": self._get_consistency_rules(),
                    })

                    if not new_eval.get("pass", False):
                        next_round_queue.append({
                            "chapter_index": chapter_index,
                            "evaluation": new_eval,
                            "round": round_num + 1
                        })
                        self.signals.log_signal.emit(
                            "Pipeline",
                            f"第{chapter_index}章第{round_num}轮修订后仍未通过，进入下一轮"
                        )
                    else:
                        self.signals.log_signal.emit(
                            "Pipeline",
                            f"第{chapter_index}章修订后通过！"
                            f"（{len(applied)} patch 生效，{len(failed)} 失败）")
                elif round_num >= max_rounds:
                    self.signals.log_signal.emit(
                        "Pipeline",
                        f"⚠️ 第{chapter_index}章已达最大修订轮数({max_rounds})，保留当前版本"
                    )

            except Exception as e:
                self.signals.log_signal.emit("Pipeline", f"⚠️ 第{chapter_index}章修订异常: {e}")

            self.signals.chapter_progress.emit(chapter_index, 100, f"修订完成(R{round_num})")

        if self._finalize_pause_if_requested():
            return

        self._revision_queue = next_round_queue

        if self._revision_queue:
            self._run_revisions()  # 递归处理下一轮
        else:
            self.signals.stage_completed.emit("回流修订")
            self.signals.log_signal.emit("Pipeline", "✅ 全部修订完成")
            self.signals.overall_progress.emit(90)
            self._adapt_chapters()

    def _adapt_chapters(self):
        """Step 5: 多平台适配"""
        if self._finalize_pause_if_requested():
            return
        self.current_stage = "adaptation"
        self.signals.stage_started.emit("多平台适配")
        self.signals.log_signal.emit("Pipeline", "📱 [5/5] 多平台适配Agent 启动...")

        agent = PlatformAdapterAgent(self.llm)
        agent.log_signal.connect(lambda name, msg: self.signals.log_signal.emit(name, msg))

        platform = "通用网文格式"  # 默认适配格式
        adapted_count = 0

        for chapter in self.chapters:
            if self._finalize_pause_if_requested():
                return
            chapter_index = chapter.get("chapter_index", 0)
            self.signals.log_signal.emit("Pipeline", f"适配第{chapter_index}章...")

            try:
                result = agent.run({
                    "content": chapter.get("content", ""),
                    "title": chapter.get("title", ""),
                    "chapter_index": chapter_index,
                    "platform": platform
                })

                self.adaptations[chapter_index] = result
                self.signals.adaptation_ready.emit(result)
                adapted_count += 1

            except Exception as e:
                self.signals.log_signal.emit("Pipeline", f"⚠️ 第{chapter_index}章适配异常: {e}")

            overall = 90 + int(((adapted_count) / len(self.chapters)) * 10)
            self.signals.overall_progress.emit(overall)

        if self._finalize_pause_if_requested():
            return

        self.signals.stage_completed.emit("多平台适配")
        self.signals.log_signal.emit("Pipeline", f"✅ 适配完成（{adapted_count}章）")

        # 流水线完成
        self._finish_pipeline()

    def _finish_pipeline(self):
        """流水线完成，汇总结果"""
        self.is_running = False
        self.current_stage = "completed"
        self.signals.overall_progress.emit(100)

        # 统计（续写场景下重新从磁盘加载全部章节，确保统计准确）
        if hasattr(self, "_continuation_new_indices") and self._continuation_new_indices:
            all_chapters = load_all_chapters(self.project_dir)
            total_words = sum(c.get("word_count", 0) for c in all_chapters)
            total_count = len(all_chapters)
        else:
            total_words = sum(c.get("word_count", 0) for c in self.chapters)
            total_count = len(self.chapters)

        avg_score = 0
        if self.evaluations:
            scores = [e.get("overall_score", 0) for e in self.evaluations.values()]
            avg_score = sum(scores) / len(scores) if scores else 0

        previous_summary = (
            load_project_summary(self.project_dir) if self.project_dir else {})

        # 续写场景：追加批次元数据，保持 status = generating（连载中）
        is_continuation = (hasattr(self, "_continuation_new_indices")
                           and self._continuation_new_indices)
        if is_continuation:
            batch_info = {
                "batch_number": self._continuation_batch,
                "guidance": self._continuation_guidance,
                "chapter_range": (f"{self._continuation_new_indices[0]}-"
                                  f"{self._continuation_new_indices[-1]}"),
                "chapter_count": len(self._continuation_new_indices),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            update_project_batches(self.project_dir, batch_info)

        # 流水线正常完成 → 状态为 completed（覆盖 paused / generating）。
        # 续写项目保持 generating 状态（连载未完）。
        if is_continuation:
            status = "generating"
        else:
            status = "completed"

        summary = {
            **previous_summary,
            "title": self.world_view.get("title", ""),
            "chapter_count": total_count,
            "chapters_count": total_count,
            "total_words": total_words,
            "avg_quality_score": round(avg_score, 1),
            "project_dir": str(self.project_dir) if self.project_dir else "",
            "status": status,
            "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 保存项目摘要
        if self.project_dir:
            save_project_summary(self.project_dir, summary)
            # 落盘时间线快照（供下次续写使用 + GUI 显示）
            try:
                snap = build_timeline_snapshot(self.project_dir)
                save_timeline_snapshot(self.project_dir, snap)
                self.signals.log_signal.emit(
                    "Pipeline",
                    f"📋 时间线快照已保存：{snap.get('total_chapters', 0)} 章，"
                    f"{len(snap.get('character_states', {}))} 角色")
            except Exception as e:
                self.signals.log_signal.emit(
                    "Pipeline", f"⚠️ 时间线快照保存失败（非致命）: {e}")

        self.signals.log_signal.emit("Pipeline", "🎉 流水线完成！")
        self.signals.log_signal.emit(
            "Pipeline",
            f"📊 统计: {total_count}章 | {total_words:,}字 | 均分{avg_score:.1f}")
        self.signals.pipeline_finished.emit(summary)

    def pause_and_save(self) -> bool:
        """请求在当前安全边界暂停，并把已完成内容落盘。"""
        if not self.is_running:
            return False
        if self._pause_requested:
            return True

        self._pause_requested = True
        self._save_pause_summary(final=False)
        self.signals.log_signal.emit(
            "Pipeline", "已请求暂停：当前模型调用完成后将保存并停止后续步骤")

        # 没有正在等待的章节 worker 时，非章节阶段可在下一个安全点收束。
        if self.current_stage == "chapter_generation" and self._pending_chapter_workers == 0:
            self._finalize_pause_if_requested()
        return True

    def _save_pause_summary(self, final: bool) -> None:
        """把暂停状态合并写入项目摘要，保留原始创作参数。"""
        if not self.project_dir:
            return
        summary = load_project_summary(self.project_dir)
        summary.update({
            "title": (self.world_view or {}).get("title", summary.get("title", "")),
            "chapter_count": self._chapter_count or summary.get("chapter_count", 0),
            "chapter_length": getattr(self, "_chapter_length", None)
                or summary.get("chapter_length", 3000),
            "status": "paused",
            "paused_stage": self.current_stage,
            "paused_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        if final:
            saved_chapters = (list(self._chapter_results.values())
                              if hasattr(self, "_chapter_results")
                              else self.chapters)
            summary["chapters_count"] = len(saved_chapters)
            summary["total_words"] = sum(
                chapter.get("word_count", 0) for chapter in saved_chapters)
        save_project_summary(self.project_dir, summary)

    def _finalize_pause_if_requested(self) -> bool:
        """在安全边界结束暂停；返回是否已经停止当前流水线。"""
        if not self._pause_requested:
            return False
        # 世界观审查 / 续写大纲审查阶段：暂停请求等用户确认后再生效
        if getattr(self, "_world_view_reviewing", False):
            return False
        if self.current_stage == "continuation_outline":
            return False
        if self.current_stage == "chapter_generation" and self._pending_chapter_workers > 0:
            return False

        self._save_pause_summary(final=True)
        self.is_running = False
        paused_stage = self.current_stage
        self.current_stage = "paused"
        self.signals.log_signal.emit("Pipeline", "✅ 项目已暂停并保存，可在项目库继续生成")
        saved_chapters = (list(self._chapter_results.values())
                          if hasattr(self, "_chapter_results")
                          else self.chapters)
        self.signals.pipeline_finished.emit({
            "paused": True,
            "title": (self.world_view or {}).get("title", ""),
            "chapters_count": len(saved_chapters),
            "total_words": sum(
                chapter.get("word_count", 0) for chapter in saved_chapters),
            "stage": paused_stage,
        })
        return True

    def _handle_error(self, message: str):
        """处理错误"""
        self.is_running = False
        self.signals.stage_error.emit(self.current_stage, message)
        self.signals.log_signal.emit("Pipeline", f"❌ {message}")
        self.signals.pipeline_finished.emit({"error": message, "stage": self.current_stage})

    def stop(self):
        """停止流水线（尽力而为）"""
        self.is_running = False
        self.signals.log_signal.emit("Pipeline", "⏹ 流水线已手动停止")

    # ------------------------------------------------------------------
    #  复跑：从已有项目状态的第一个未完成阶段继续
    # ------------------------------------------------------------------
    def resume_from_project(self, project_dir):
        """
        从历史项目目录恢复运行：缺大纲先生成大纲，否则只补缺失章节。
        project_dir: str 或 Path
        """
        from pathlib import Path as _Path
        project_dir = _Path(project_dir)

        title = project_dir.name
        self.signals.log_signal.emit(
            "Pipeline", f"🔁 恢复项目: {project_dir.name}")

        # 加载 state
        world_view = load_world_view(project_dir)
        if not world_view or not isinstance(world_view, dict):
            raise RuntimeError("项目 world_view.json 缺失或损坏")

        coarse_outline = world_view.get("chapter_outline", [])
        if not isinstance(coarse_outline, list) or not coarse_outline:
            raise RuntimeError("项目 world_view.json 中没有可用的章节大纲")

        existing = load_all_chapters_map(project_dir)
        outline = load_outline(project_dir)
        project_summary = load_project_summary(project_dir)

        # 初始化 pipeline 状态
        if not self.llm:
            self.initialize()
        self.is_running = True
        self._pause_requested = False
        self.project_dir = project_dir
        self.world_view = world_view
        self.outline = outline
        saved_length = project_summary.get("chapter_length")
        try:
            self._chapter_length = int(saved_length)
        except (TypeError, ValueError):
            self._chapter_length = self.config.get("default_chapter_length", 3000)

        if not self._outline_is_complete(outline, coarse_outline):
            self.outline = None
            self.signals.log_signal.emit(
                "Pipeline", "▶️ 断点位于大纲生成：未找到完整 outline.json，开始恢复大纲")

            # 大纲生成会调用模型，放到后台线程，避免从项目库恢复时阻塞界面。
            import threading
            self._pipeline_thread = threading.Thread(
                target=self._build_outline,
                args=(world_view,),
                kwargs={"resume_existing": existing},
                daemon=True,
            )
            self._pipeline_thread.start()
            return

        # 章节补全 / 质量评估 / 修订均可能调用模型，放到后台线程，避免阻塞界面。
        import threading
        def _resume_worker():
            try:
                self._resume_chapter_generation(existing)
            except Exception as e:
                self._handle_error(f"恢复章节生成异常: {e}")
        self._pipeline_thread = threading.Thread(
            target=_resume_worker,
            daemon=True,
        )
        self._pipeline_thread.start()

    def _merge_existing_chapters(self, existing: dict):
        """把已有章节预填进 self.chapters / self._chapter_results，用于续写场景。"""
        merged = {
            index - 1: chapter
            for index, chapter in existing.items()
            if isinstance(index, int)
        }
        self._chapter_results = merged
        self.chapters = [existing[index] for index in sorted(existing)
                         if isinstance(index, int)]
        self._chapter_completed_count = len(existing)
        self._completed_chapters = len(existing)

    # ------------------------------------------------------------------
    #  续写：从已有项目的"下一个批次"重新进入流水线
    # ------------------------------------------------------------------
    def continue_from_project(self, project_dir, guidance: str,
                              batch_chapter_count: int = None,
                              chapter_length: int = None):
        """
        启动续写流程：仅生成"下一批"的新大纲，产出后暂停等待用户审阅。

        流程：加载遗产包 → 调 ContinuationOutlineAgent → 暂停(continuation_outline_ready)
              → 用户审阅确认后调 confirm_continuation() 开始写章节

        project_dir: str 或 Path
        guidance: 用户给的本批续写方向指引（必填）
        batch_chapter_count: 本批章数（默认取 config.default_chapter_count）
        chapter_length: 每章字数（默认沿用项目设定）
        """
        from pathlib import Path as _Path
        import threading
        project_dir = _Path(project_dir)

        if not guidance or not guidance.strip():
            raise RuntimeError("续写指引不能为空")

        if self.is_running:
            self.signals.log_signal.emit("Pipeline", "⚠️ 流水线已在运行中")
            return
        if not self.llm:
            self.initialize()

        # 加载项目基本信息
        world_view = load_world_view(project_dir)
        if not world_view:
            raise RuntimeError("项目 world_view.json 缺失或损坏")

        # 参数准备
        project_summary = load_project_summary(project_dir)
        if batch_chapter_count is None:
            batch_chapter_count = self.config.get("default_chapter_count", 10)
        if chapter_length is None:
            saved_length = project_summary.get("chapter_length")
            try:
                chapter_length = int(saved_length)
            except (TypeError, ValueError):
                chapter_length = self.config.get("default_chapter_length", 3000)

        # 初始化续写状态
        self.is_running = True
        self._pause_requested = False
        self.project_dir = project_dir
        self.world_view = world_view
        self._chapter_length = chapter_length
        self._continuation_guidance = guidance
        self._continuation_batch = get_next_batch_number(project_dir)

        self.signals.log_signal.emit(
            "Pipeline",
            f"🔁 续写启动 | 批次 #{self._continuation_batch} | "
            f"指引: {guidance[:30]}... | {batch_chapter_count}章")

        # 生成大纲是 LLM 调用，放后台线程
        def _run_continuation_outline():
            try:
                self._build_continuation_outline(batch_chapter_count)
            except Exception as e:
                self.signals.log_signal.emit("Pipeline", f"❌ 续写字大纲异常: {e}")
                self.is_running = False

        self._pipeline_thread = threading.Thread(
            target=_run_continuation_outline, daemon=True)
        self._pipeline_thread.start()

    def _build_continuation_outline(self, batch_chapter_count: int):
        """加载遗产包 → 调续写大纲 Agent → 暂停等待审阅。"""
        self.current_stage = "continuation_outline"
        self.signals.stage_started.emit("续写大纲生成")
        self.signals.continuation_progress.emit("加载遗产包...", 5)
        self.signals.log_signal.emit(
            "Pipeline", f"📦 [续写] 加载遗产包...")

        # 加载遗产包
        legacy = load_legacy_package(self.project_dir, recent_n=3)
        self._continuation_legacy = legacy

        existing_count = legacy.get("existing_chapters_count", 0)
        self.signals.log_signal.emit(
            "Pipeline",
            f"📦 遗产包加载完成：已有 {existing_count} 章，"
            f"{len(legacy.get('existing_rules', []))} 条旧规则，"
            f"{len(legacy.get('unresolved_foreshadowing', []))} 条未回收伏笔")

        # 调续写大纲 Agent
        self.signals.continuation_progress.emit("生成续写大纲...", 30)
        agent = ContinuationOutlineAgent(
            self.llm,
            temperature=self.config.get("outline_temperature", 0.7),
            max_tokens=self.config.get("outline_max_tokens", 8192),
        )
        agent.log_signal.connect(
            lambda name, msg: self.signals.log_signal.emit(name, msg))
        agent.progress_signal.connect(
            lambda name, pct: self.signals.continuation_progress.emit(
                "生成续写大纲...", 30 + int(pct * 0.6)))

        input_data = {
            "legacy_package": legacy,
            "guidance": self._continuation_guidance,
            "batch_chapter_count": batch_chapter_count,
            "chapter_length": self._chapter_length,
        }

        try:
            outline = agent.run(input_data)
        except Exception as e:
            self.signals.stage_error.emit("续写大纲生成", str(e))
            self._handle_error(f"续写大纲生成异常: {e}")
            return

        if "error" in outline:
            self.signals.stage_error.emit("续写大纲生成", outline["error"])
            self._handle_error(f"续写大纲生成失败: {outline['error']}")
            return

        # 注入批次号
        outline.setdefault("outline_meta", {})
        outline["outline_meta"]["batch"] = self._continuation_batch

        # 缓存并保存大纲（这样即使 UI 关闭对话框，大纲也不会丢）
        self._continuation_outline = outline
        self._outline_for_chapters = outline
        save_batch_outline(
            self.project_dir, self._continuation_batch, outline)

        start_idx = outline["outline_meta"].get("chapter_start", existing_count + 1)
        end_idx = outline["outline_meta"].get("chapter_end", existing_count + batch_chapter_count)
        self.signals.log_signal.emit(
            "Pipeline",
            f"✅ 续写大纲生成完成（第 {start_idx}-{end_idx} 章）— 等待用户审阅")

        self.signals.continuation_progress.emit("等待审阅...", 100)
        # 发射信号 → UI 弹出审阅对话框
        self.signals.continuation_outline_ready.emit(outline)

    def confirm_continuation(self, reviewed_outline: dict):
        """
        用户审阅确认后，用审阅过的大纲开始生成章节。
        由 UI 在 OutlineReviewDialog 确认后调用。
        """
        if not self.is_running:
            self.signals.log_signal.emit("Pipeline", "⚠️ 流水线已停止，无法启动章节生成")
            return

        # 用用户审阅过的大纲替换缓存
        self._continuation_outline = reviewed_outline
        self._outline_for_chapters = reviewed_outline
        save_batch_outline(
            self.project_dir, self._continuation_batch, reviewed_outline)

        start_idx = reviewed_outline.get("outline_meta", {}).get("chapter_start", 0)
        end_idx = reviewed_outline.get("outline_meta", {}).get("chapter_end", 0)
        self.signals.log_signal.emit(
            "Pipeline",
            f"▶️ 用户确认续写大纲，开始生成第 {start_idx}-{end_idx} 章...")

        # 章节生成调用模型，放到后台线程，避免阻塞界面
        import threading
        def _run_chapters():
            try:
                self._generate_continuation_chapters(reviewed_outline)
            except Exception as e:
                self._handle_error(f"续写章节生成异常: {e}")
        self._pipeline_thread = threading.Thread(
            target=_run_chapters, daemon=True)
        self._pipeline_thread.start()

    def _generate_continuation_chapters(self, outline: dict):
        """用审阅后的续写大纲并行生成章节。"""
        self.current_stage = "chapter_generation"
        self.signals.stage_started.emit("章节生成")

        batch_start = outline.get("outline_meta", {}).get("chapter_start", 1)
        chapter_count = outline["outline_meta"].get("total_chapters", 0)
        existing_count = batch_start - 1

        self.signals.log_signal.emit(
            "Pipeline",
            f"✍️ [续写] 并行生成第 {batch_start}-{batch_start + chapter_count - 1} 章...")

        # 章节 agent 需要的大纲上下文（含所有历史批次，保证连贯）
        outline_context = self._build_continuation_outline_context()
        outline_detail_map = {
            ch.get("chapter_index"): ch
            for ch in outline.get("chapters", [])
        }

        # 预填旧章节（让 self.chapters 在评估/修订阶段包含完整列表）
        existing_chapters = load_all_chapters_map(self.project_dir)
        self._merge_existing_chapters(existing_chapters)
        self._continuation_old_count = existing_count
        self._continuation_new_indices = list(range(batch_start, batch_start + chapter_count))

        import threading
        concurrency = self.config.get("concurrency", 3)
        self._semaphore = threading.Semaphore(concurrency)
        self._chapter_lock = threading.Lock()
        self._total_chapters = chapter_count
        self._pending_chapter_workers = chapter_count
        self._completed_chapters = 0

        for i, outline_entry in enumerate(outline.get("chapters", [])):
            chapter_index = outline_entry.get("chapter_index", batch_start + i)

            # 前情提要：优先取同批前一章的实际 summary，否则回退到遗产包最后一章
            prev_summary = ""
            if i > 0 and (i - 1) in self._chapter_results:
                prev_summary = self._chapter_results[i - 1].get("summary", "")
            elif existing_count > 0:
                legacy_recent = self._continuation_legacy.get(
                    "recent_chapters", []) if self._continuation_legacy else []
                if legacy_recent:
                    prev_summary = legacy_recent[-1].get("summary", "")

            outline_ch = outline_detail_map.get(chapter_index, outline_entry)

            input_data = {
                "world_view": self.world_view,
                "chapter_outline": outline_entry,
                "chapter_index": chapter_index,
                "target_length": self._chapter_length,
                "previous_chapter_summary": prev_summary,
                "outline_chapter": outline_ch,
                "outline_context": outline_context,
                "character_arcs": outline.get("character_arcs", {}),
            }

            threading.Thread(
                target=self._gen_chapter_worker,
                args=(i, input_data),
                daemon=True,
            ).start()

    def _build_continuation_outline_context(self) -> dict:
        """构建续写章节生成用的大纲上下文，合并所有历史批次的信息。"""
        # 收集所有批次的一致性规则（去重保序）
        all_rules = []
        for _, batch_outline in list_batch_outlines(self.project_dir):
            for r in batch_outline.get("consistency_rules", []):
                if r not in all_rules:
                    all_rules.append(r)
        # 批次大纲没有旧规则时（兼容第一批续写），也带上原始 outline.json 的规则
        base_outline = load_outline(self.project_dir)
        if base_outline:
            for r in base_outline.get("consistency_rules", []):
                if r not in all_rules:
                    all_rules.append(r)

        # 所有批次的章节 summary（供每章 agent 感知前后走向）
        all_summary = []
        for _, batch_outline in list_batch_outlines(self.project_dir):
            for ch in batch_outline.get("chapters", []):
                all_summary.append({
                    "chapter_index": ch.get("chapter_index"),
                    "title": ch.get("title", ""),
                    "plot_detail": ch.get("plot_detail", ""),
                    "foreshadowing": ch.get("foreshadowing", []),
                })
        # 也补上原始 outline.json 的章节
        if base_outline:
            for ch in base_outline.get("chapters", []):
                if not any(s.get("chapter_index") == ch.get("chapter_index") for s in all_summary):
                    all_summary.append({
                        "chapter_index": ch.get("chapter_index"),
                        "title": ch.get("title", ""),
                        "plot_detail": ch.get("plot_detail", ""),
                        "foreshadowing": ch.get("foreshadowing", []),
                    })
        all_summary.sort(key=lambda s: s.get("chapter_index", 0))

        return {
            "consistency_rules": all_rules,
            "global_arc": (self._outline_for_chapters or {}).get("global_arc", {}),
            "all_chapters_summary": all_summary,
        }

    def discard_continuation(self):
        """用户取消续写时调用，清理状态并恢复项目。"""
        self.is_running = False
        self.current_stage = "idle"
        # 如果已保存了未使用的大纲文件，保留（用户可以后续手动恢复）
        self._continuation_outline = None
        self._continuation_guidance = ""
        self.signals.log_signal.emit("Pipeline", "❌ 续写已取消")

    # ------------------------------------------------------------------
    #  世界观审查
    # ------------------------------------------------------------------
    def confirm_world_view(self, reviewed_world_view: dict):
        """
        用户在 WorldViewReviewDialog 审阅确认后调用。
        用审阅后的世界观替换 self.world_view，进入大纲生成阶段。
        """
        if not self.is_running and not getattr(self, "_world_view_reviewing", False):
            self.signals.log_signal.emit(
                "Pipeline", "⚠️ 流水线已停止，无法确认世界观")
            return

        self.world_view = reviewed_world_view
        self._pending_world_view = None
        self._world_view_reviewing = False

        # 用审阅后的世界观覆盖落盘
        if self.project_dir:
            save_world_view(self.project_dir, reviewed_world_view)
            # 更新 summary 的标题（用户可能改了书名）
            try:
                summary = load_project_summary(self.project_dir)
                summary["title"] = reviewed_world_view.get("title",
                                                           summary.get("title", ""))
                save_project_summary(self.project_dir, summary)
            except Exception:
                pass

        title = reviewed_world_view.get("title", "")
        self.signals.log_signal.emit(
            "Pipeline", f"▶️ 用户确认世界观《{title}》，启动大纲生成...")

        # 进入大纲生成（大纲生成调用模型，放到后台线程，避免阻塞界面）
        if self._finalize_pause_if_requested():
            return
        import threading
        self._pipeline_thread = threading.Thread(
            target=self._build_outline,
            args=(reviewed_world_view,),
            daemon=True,
        )
        self._pipeline_thread.start()

    def discard_world_view(self):
        """用户取消世界观审阅时调用 — 取消本次生成，回到空闲。"""
        self.is_running = False
        self.current_stage = "idle"
        self._pending_world_view = None
        self._world_view_reviewing = False
        self.world_view = None
        self.signals.log_signal.emit(
            "Pipeline", "❌ 用户取消世界观审阅，本次生成已取消")

    def export_txt(self, output_path: str) -> bool:
        """导出txt"""
        if self.project_dir:
            return export_to_txt(self.project_dir, output_path)
        return False

    def export_markdown(self, output_path: str) -> bool:
        """导出Markdown"""
        if self.project_dir:
            return export_to_markdown(self.project_dir, output_path)
        return False

    def get_status(self) -> dict:
        """获取当前流水线状态（供Web面板轮询）"""
        return {
            "is_running": self.is_running,
            "current_stage": self.current_stage,
            "total_chapters": self._chapter_count,
            "completed_chapters": self._completed_chapters,
            "world_view": self.world_view,
            "outline": self.outline,
            "chapters": self.chapters,
            "evaluations": {str(k): v for k, v in self.evaluations.items()},
            "adaptations_count": len(self.adaptations),
            "project_dir": str(self.project_dir) if self.project_dir else None
        }
