"""Flask Web 服务器 - 港口集卡调度系统可视化平台。

提供 REST API 和 Web 界面，将仿真计算与前端渲染分离。
"""

import json
import threading
import time
import sys
import os

from flask import Flask, render_template, jsonify, request

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulation import PortSimApp

app = Flask(__name__)
sim_app = None
sim_thread = None
sim_lock = threading.Lock()
auto_run = False
auto_speed = 0.05  # seconds per step


def create_app(num_trucks=4, port_cols=8, port_rows=3,
               use_ml=True, use_congestion=True, use_rl=True):
    global sim_app
    sim_app = PortSimApp(
        num_trucks=num_trucks,
        port_cols=port_cols,
        port_rows=port_rows,
        use_ml_predictor=use_ml,
        use_congestion_prediction=use_congestion,
        use_rl=use_rl
    )
    return sim_app


def auto_run_loop():
    global auto_run, sim_app
    while auto_run:
        with sim_lock:
            if sim_app:
                sim_app.step_once()
        time.sleep(auto_speed)


# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    with sim_lock:
        if sim_app is None:
            return jsonify({"error": "Simulation not initialized"}), 400
        state = sim_app.get_state_dict()
        # Convert numpy types
        return jsonify(_sanitize(state))


@app.route("/api/step", methods=["POST"])
def api_step():
    global sim_app
    with sim_lock:
        if sim_app is None:
            return jsonify({"error": "Simulation not initialized"}), 400
        steps = request.json.get("steps", 1) if request.is_json else 1
        for _ in range(steps):
            sim_app.step_once()
    return jsonify({"ok": True, "step": sim_app.step_count})


@app.route("/api/reset", methods=["POST"])
def api_reset():
    global sim_app, auto_run
    auto_run = False
    with sim_lock:
        if sim_app:
            sim_app.reset()
    return jsonify({"ok": True})


@app.route("/api/auto", methods=["POST"])
def api_auto():
    global auto_run, auto_speed
    data = request.json if request.is_json else {}
    action = data.get("action", "toggle")

    if action == "start":
        auto_run = True
        if sim_thread is None or not sim_thread.is_alive():
            t = threading.Thread(target=auto_run_loop, daemon=True)
            t.start()
    elif action == "stop":
        auto_run = False
    elif action == "toggle":
        auto_run = not auto_run
        if auto_run:
            t = threading.Thread(target=auto_run_loop, daemon=True)
            t.start()

    if "speed" in data:
        auto_speed = data["speed"]

    return jsonify({"auto_run": auto_run, "speed": auto_speed})


@app.route("/api/tasks/add", methods=["POST"])
def api_add_task():
    with sim_lock:
        if sim_app is None:
            return jsonify({"error": "Simulation not initialized"}), 400
        new_task = sim_app.gen.create_random_tasks(num=1, current_step=sim_app.step_count)[0]
        new_task.id = f"T{len(sim_app.manager.queue) + 1:02d}"
        sim_app.manager.queue.append(new_task)
    return jsonify({"ok": True, "task": str(new_task)})


@app.route("/api/benchmark", methods=["POST"])
def api_benchmark():
    global sim_app
    with sim_lock:
        if sim_app is None:
            return jsonify({"error": "Simulation not initialized"}), 400
        steps = request.json.get("steps", 200) if request.is_json else 200
        result = sim_app.run_benchmark(steps=steps)
    return jsonify(_sanitize(result))


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    global sim_app, auto_speed
    if request.method == "POST":
        data = request.json if request.is_json else {}
        if "ml_enabled" in data and sim_app:
            sim_app.use_ml_predictor = data["ml_enabled"]
        if "congestion_enabled" in data and sim_app:
            sim_app.use_congestion_prediction = data["congestion_enabled"]
        if "speed" in data:
            auto_speed = data["speed"]
        return jsonify({"ok": True})

    return jsonify({
        "ml_enabled": sim_app.use_ml_predictor if sim_app else False,
        "congestion_enabled": sim_app.use_congestion_prediction if sim_app else False,
        "speed": auto_speed,
        "num_trucks": sim_app.num_trucks if sim_app else 0
    })


def _sanitize(obj):
    """Recursively convert numpy types to native Python for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    elif hasattr(obj, "item"):
        return obj.item()
    elif hasattr(obj, "tolist"):
        return obj.tolist()
    return obj


def run_server(num_trucks=4, port_cols=8, port_rows=3,
               use_ml_predictor=True, use_congestion_prediction=True,
               use_rl=True, host="127.0.0.1", port=5000):
    """入口函数，供 main.py 调用。"""
    create_app(
        num_trucks=num_trucks,
        port_cols=port_cols,
        port_rows=port_rows,
        use_ml=use_ml_predictor,
        use_congestion=use_congestion_prediction,
        use_rl=use_rl
    )
    print(f"Port dispatch web server running at http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    create_app()
    print("Starting development server at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
