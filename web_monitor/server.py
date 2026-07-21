"""
Flask Web监控面板服务
与GUI共享流水线状态，通过/poll端点提供JSON数据
"""

import threading
import json
from flask import Flask, jsonify, render_template_string

# 全局状态（由pipeline引擎更新）
_pipeline_status = {
    "is_running": False,
    "current_stage": "idle",
    "total_chapters": 0,
    "completed_chapters": 0,
    "overall_progress": 0,
    "title": "",
    "log_buffer": [],
    "agent_status": {},
    "stats": {}
}
_status_lock = threading.Lock()
_max_log_lines = 500


def update_status(key: str, value):
    """线程安全地更新状态"""
    with _status_lock:
        _pipeline_status[key] = value


def append_log(source: str, message: str):
    """追加日志到缓冲区"""
    import time
    with _status_lock:
        _pipeline_status["log_buffer"].append({
            "time": time.strftime("%H:%M:%S"),
            "source": source,
            "message": message
        })
        # 限制日志数量
        if len(_pipeline_status["log_buffer"]) > _max_log_lines:
            _pipeline_status["log_buffer"] = _pipeline_status["log_buffer"][-_max_log_lines:]


def update_progress(value: int):
    """更新整体进度"""
    with _status_lock:
        _pipeline_status["overall_progress"] = value


def update_agent_status(name: str, status: str):
    """更新Agent状态"""
    with _status_lock:
        _pipeline_status["agent_status"][name] = status


def get_full_status() -> dict:
    """获取完整状态（线程安全拷贝）"""
    with _status_lock:
        return json.loads(json.dumps(_pipeline_status))


def create_app() -> Flask:
    """创建Flask应用"""
    app = Flask(__name__, template_folder="templates")

    @app.route("/")
    def dashboard():
        return render_template_string(DASHBOARD_HTML)

    @app.route("/api/status")
    def api_status():
        return jsonify(get_full_status())

    @app.route("/api/logs")
    def api_logs():
        with _status_lock:
            logs = list(_pipeline_status["log_buffer"])
        return jsonify(logs)

    return app


def start_server(port: int = 5000, debug: bool = False):
    """在后台线程启动Flask服务"""
    app = create_app()

    def run():
        app.run(host="127.0.0.1", port=port, debug=debug, use_reloader=False)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


# ===== 内嵌HTML监控面板 =====
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI小说工厂 - 监控面板</title>
    <style>
        * {margin: 0; padding: 0; box-sizing: border-box;}
        body {
            font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
            background: #0a0a1a;
            color: #e0e0e0;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #0f3460 0%, #16213e 100%);
            padding: 15px 25px;
            display: flex;
            align-items: center;
            gap: 15px;
            border-bottom: 2px solid #00d4ff;
        }
        .header h1 {color: #00d4ff; font-size: 20px;}
        .status-badge {
            background: #333;
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 12px;
            color: #888;
        }
        .status-badge.running {background: #004400; color: #00ff88;}
        .status-badge.idle {background: #333; color: #888;}
        .container {padding: 20px; max-width: 1400px; margin: 0 auto;}

        /* 统计卡片 */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: #1a1a2e;
            border: 1px solid #2d2d44;
            border-radius: 10px;
            padding: 15px;
            text-align: center;
        }
        .stat-card .value {
            font-size: 28px;
            font-weight: bold;
            color: #00d4ff;
        }
        .stat-card .label {
            font-size: 12px;
            color: #888;
            margin-top: 5px;
        }

        /* 进度条 */
        .progress-section {
            background: #1a1a2e;
            border: 1px solid #2d2d44;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .progress-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        .progress-bar-bg {
            background: #0f3460;
            border-radius: 6px;
            height: 22px;
            overflow: hidden;
        }
        .progress-bar-fill {
            background: linear-gradient(90deg, #0066cc, #00d4ff);
            height: 100%;
            border-radius: 6px;
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            color: white;
        }

        /* Agent网格 */
        .agent-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-bottom: 20px;
        }
        .agent-item {
            background: #1a1a2e;
            border: 1px solid #2d2d44;
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }
        .agent-item .agent-name {font-size: 12px; color: #aaa;}
        .agent-item .agent-status {
            font-size: 11px;
            margin-top: 5px;
            padding: 2px 8px;
            border-radius: 10px;
            display: inline-block;
        }
        .agent-status.idle {background: #333; color: #888;}
        .agent-status.running {background: #003366; color: #00d4ff;}
        .agent-status.success {background: #003322; color: #00ff88;}
        .agent-status.error {background: #330000; color: #ff4444;}

        /* 日志区 */
        .log-section {
            background: #0a0a1a;
            border: 1px solid #2d2d44;
            border-radius: 10px;
            max-height: 400px;
            overflow-y: auto;
        }
        .log-section h3 {
            padding: 12px 15px;
            border-bottom: 1px solid #2d2d44;
            color: #00d4ff;
            position: sticky;
            top: 0;
            background: #0a0a1a;
        }
        .log-line {
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 11px;
            padding: 3px 15px;
            border-bottom: 1px solid #111;
        }
        .log-line .log-time {color: #555; margin-right: 8px;}
        .log-line .log-source {color: #00d4ff; margin-right: 8px;}
        .log-line .log-msg {color: #ccc;}

        /* 阶段指示器 */
        .stages {
            display: flex;
            gap: 8px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        .stage-tag {
            background: #1a1a2e;
            border: 1px solid #2d2d44;
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 12px;
            color: #888;
        }
        .stage-tag.active {border-color: #00d4ff; color: #00d4ff; background: #001133;}
        .stage-tag.done {border-color: #00ff88; color: #00ff88; background: #002200;}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 AI小说工厂 监控台</h1>
        <span id="statusBadge" class="status-badge idle">空闲</span>
    </div>

    <div class="container">
        <!-- 统计 -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="value" id="statProgress">0%</div>
                <div class="label">整体进度</div>
            </div>
            <div class="stat-card">
                <div class="value" id="statChapters">0</div>
                <div class="label">总章节</div>
            </div>
            <div class="stat-card">
                <div class="value" id="statCompleted">0</div>
                <div class="label">已完成</div>
            </div>
            <div class="stat-card">
                <div class="value" id="statStage">-</div>
                <div class="label">当前阶段</div>
            </div>
        </div>

        <!-- 进度条 -->
        <div class="progress-section">
            <div class="progress-header">
                <span>流水线进度</span>
                <span id="progressText">等待启动</span>
            </div>
            <div class="progress-bar-bg">
                <div id="progressBar" class="progress-bar-fill" style="width:0%">0%</div>
            </div>
        </div>

        <!-- 阶段指示器 -->
        <div class="stages">
            <div class="stage-tag" id="stage_world">① 世界观</div>
            <div class="stage-tag" id="stage_outline">② 大纲生成</div>
            <div class="stage-tag" id="stage_chapter">③ 章节生成</div>
            <div class="stage-tag" id="stage_eval">④ 质量评估</div>
            <div class="stage-tag" id="stage_revision">⑤ 回流修订</div>
            <div class="stage-tag" id="stage_adapt">⑥ 平台适配</div>
        </div>

        <!-- Agent状态 -->
        <div class="agent-grid" id="agentGrid">
            <div class="agent-item">
                <div class="agent-name">流水线</div>
                <div class="agent-status idle" id="agent-pipeline">空闲</div>
            </div>
        </div>

        <!-- 日志 -->
        <div class="log-section" id="logSection">
            <h3>📋 实时日志</h3>
            <div id="logContainer"></div>
        </div>
    </div>

    <script>
        const STAGES = ['world_building', 'outline_generation', 'chapter_generation', 'quality_evaluation', 'revision', 'adaptation', 'completed'];
        const STAGE_NAMES = {
            'world_building': '世界观构建',
            'outline_generation': '大纲生成',
            'chapter_generation': '章节生成',
            'quality_evaluation': '质量评估',
            'revision': '回流修订',
            'adaptation': '平台适配',
            'completed': '已完成',
            'idle': '空闲'
        };
        const STAGE_IDS = {
            'world_building': 'stage_world',
            'outline_generation': 'stage_outline',
            'chapter_generation': 'stage_chapter',
            'quality_evaluation': 'stage_eval',
            'revision': 'stage_revision',
            'adaptation': 'stage_adapt'
        };

        let lastLogCount = 0;

        async function fetchStatus() {
            try {
                const resp = await fetch('/api/status');
                const data = await resp.json();
                updateUI(data);
            } catch(e) {
                // 服务不可用时静默处理
            }
        }

        function updateUI(data) {
            // 状态徽章
            const badge = document.getElementById('statusBadge');
            if (data.is_running) {
                badge.textContent = '运行中';
                badge.className = 'status-badge running';
            } else {
                badge.textContent = '空闲';
                badge.className = 'status-badge idle';
            }

            // 统计
            document.getElementById('statProgress').textContent = data.overall_progress + '%';
            document.getElementById('statChapters').textContent = data.total_chapters;
            document.getElementById('statCompleted').textContent = data.completed_chapters;
            document.getElementById('statStage').textContent = STAGE_NAMES[data.current_stage] || data.current_stage;

            // 进度条
            const bar = document.getElementById('progressBar');
            bar.style.width = data.overall_progress + '%';
            bar.textContent = data.overall_progress + '%';
            document.getElementById('progressText').textContent =
                data.title ? `《${data.title}》` : '等待启动';

            // 阶段指示器
            const currentIdx = STAGES.indexOf(data.current_stage);
            STAGES.forEach((stage, idx) => {
                const el = document.getElementById(STAGE_IDS[stage]);
                if (!el) return;
                el.className = 'stage-tag';
                if (idx < currentIdx || data.current_stage === 'completed') {
                    el.classList.add('done');
                } else if (idx === currentIdx) {
                    el.classList.add('active');
                }
            });

            // Agent状态
            const agentGrid = document.getElementById('agentGrid');
            agentGrid.innerHTML = '';
            for (const [name, status] of Object.entries(data.agent_status || {})) {
                const displayName = name.length > 8 ? name.slice(0, 8) + '..' : name;
                const statusText = {idle: '空闲', running: '运行中', success: '完成', error: '失败', waiting: '等待'}[status] || status;
                agentGrid.innerHTML += `
                    <div class="agent-item">
                        <div class="agent-name">${displayName}</div>
                        <div class="agent-status ${status}">${statusText}</div>
                    </div>`;
            }

            // 日志（仅追加新日志）
            if (data.log_buffer && data.log_buffer.length > lastLogCount) {
                const container = document.getElementById('logContainer');
                const newLogs = data.log_buffer.slice(lastLogCount);
                newLogs.forEach(log => {
                    container.innerHTML += `
                        <div class="log-line">
                            <span class="log-time">[${log.time}]</span>
                            <span class="log-source">[${log.source}]</span>
                            <span class="log-msg">${escapeHtml(log.message)}</span>
                        </div>`;
                });
                lastLogCount = data.log_buffer.length;
                container.scrollTop = container.scrollHeight;
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // 每2秒轮询
        setInterval(fetchStatus, 2000);
        fetchStatus();  // 立即执行一次
    </script>
</body>
</html>
"""
