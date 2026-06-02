import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from draw_port import AdvancedRealisticPort
from tasks import TaskGenerator, TaskManager
from truck import Truck
from path_planning import a_star_search
from congestion_predictor import CongestionPredictor
from task_value_predictor import TaskValuePredictor
import numpy as np
import random
import math
import time
from scipy.optimize import linear_sum_assignment


class PortSimApp:
    def __init__(self, num_trucks=4, port_cols=8, port_rows=3,
                 use_ml_predictor=True, use_congestion_prediction=True,
                 headless=False):
        # Port
        self.port = AdvancedRealisticPort(seed=42)
        self.port.generate(num_cols=port_cols, num_rows=port_rows, yard_prob=0.7)
        self.gen = TaskGenerator(self.port)
        self.manager = TaskManager([])

        # Intelligent modules
        self.use_ml_predictor = use_ml_predictor
        self.use_congestion_prediction = use_congestion_prediction
        self.task_predictor = TaskValuePredictor() if use_ml_predictor else None
        self.congestion_predictor = CongestionPredictor() if use_congestion_prediction else None

        if self.congestion_predictor:
            self.congestion_predictor.set_node_coords_cache(self.port.nodes)

        # Trucks
        self.trucks = []
        self.num_trucks = num_trucks
        colors = ['red', 'blue', 'green', 'purple', 'darkorange',
                  'brown', 'pink', 'olive', 'cyan', 'magenta']
        start_node_pos = self.port.nodes['Gate_In']

        for i in range(num_trucks):
            offset = np.array([random.uniform(-2, 2), random.uniform(-2, 2)])
            t = Truck(i + 1,
                      np.array(start_node_pos, dtype=np.float64) + offset,
                      colors[i % len(colors)])
            self.trucks.append(t)

        # Simulation state
        self.step_count = 0
        self.dispatch_interval = 3  # 每 N 步执行一次匈牙利分配
        self.auto_task_timer = 0
        self.auto_task_interval = 15
        self.max_tasks = 20
        self.running = True

        # Stats
        self.total_completed = 0
        self.total_wait_time = 0.0
        self.start_time = time.time()
        self.metrics_history = []

        # Visualization (matplotlib mode)
        self.headless = headless
        self.fig = None
        self.ax = None
        self.btn_add = None

        if not headless:
            self._init_visualization()

        # Generate initial tasks
        initial_tasks = self.gen.create_random_tasks(num=5)
        for i, t in enumerate(initial_tasks):
            t.id = f"T{i + 1:02d}"
        self.manager.queue.extend(initial_tasks)

    # -----------------------------
    # Visualization setup
    # -----------------------------
    def _init_visualization(self):
        self.fig, self.ax = plt.subplots(figsize=(14, 9))
        plt.subplots_adjust(bottom=0.18)

        ax_btn1 = plt.axes([0.15, 0.04, 0.14, 0.05])
        self.btn_add = Button(ax_btn1, '添加任务',
                              color='lightgray', hovercolor='skyblue')
        self.btn_add.on_clicked(self._on_add_task)

        ax_btn2 = plt.axes([0.32, 0.04, 0.14, 0.05])
        self.btn_toggle = Button(ax_btn2, 'ML开关',
                                 color='lightgray', hovercolor='skyblue')
        self.btn_toggle.on_clicked(self._on_toggle_mode)

        ax_btn3 = plt.axes([0.49, 0.04, 0.14, 0.05])
        self.btn_bench = Button(ax_btn3, '性能测试',
                                color='#e74c3c', hovercolor='#c0392b')
        self.btn_bench.on_clicked(self._on_benchmark)

    def _on_add_task(self, event):
        if len(self.manager.get_pending_tasks()) >= self.max_tasks:
            print(f"Task queue full (max {self.max_tasks})")
            return
        new_task = self.gen.create_random_tasks(num=1)[0]
        new_task.id = f"T{len(self.manager.queue) + 1:02d}"
        self.manager.queue.append(new_task)

    def _on_toggle_mode(self, event):
        self.use_ml_predictor = not self.use_ml_predictor
        mode = "ML增强" if self.use_ml_predictor else "纯距离"
        print(f"切换模式: {mode}")

    def _on_benchmark(self, event):
        """Matplotlib模式：逐步运行1000步，实时显示画面。"""
        print("\n" + "=" * 60)
        print("          性能测试 — 运行1000步仿真")
        print("=" * 60)

        if self.headless:
            self.run_benchmark(steps=1000)
            return

        completed_before = self.total_completed
        t0 = time.time()

        for i in range(1000):
            self.update_logic()
            # 实时刷新画面
            self._render_frame()
            plt.pause(0.005)

        elapsed = time.time() - t0

        stats = self.manager.get_stats()
        utilization = np.mean([t.get_utilization() for t in self.trucks])
        hotspots = self.congestion_predictor.get_hotspot_list() if self.congestion_predictor else []
        tasks_done = self.total_completed - completed_before
        mode = "ML增强" if self.use_ml_predictor else "纯距离"
        congestion = "开" if self.use_congestion_prediction else "关"

        print(f"  测试步数:       1000")
        print(f"  真实耗时:       {elapsed:.1f}秒")
        print(f"  任务完成数:     {tasks_done} (总计: {stats['completed']})")
        print(f"  待处理任务:     {stats['pending']}")
        print(f"  平均等待时间:   {stats['avg_wait_time']}秒")
        print(f"  车辆利用率:     {utilization:.1%}")
        print(f"  拥堵热点数:     {len(hotspots)}")
        print(f"  调度模式:       {mode} | 拥堵预测: {congestion}")
        print(f"  车辆详情:")
        for t in self.trucks:
            print(f"    卡车{t.id}: 状态={t.status}  利用率={t.get_utilization():.1%}  "
                  f"行程数={t.trip_count}")
        print("=" * 60 + "\n")

    def run_benchmark(self, steps=200):
        """运行性能测试，输出格式化结果。"""
        start_step = self.step_count
        completed_before = self.total_completed

        t0 = time.time()
        for _ in range(steps):
            self.step_once()
        elapsed = time.time() - t0

        stats = self.manager.get_stats()
        utilization = np.mean([t.get_utilization() for t in self.trucks])
        hotspots = self.congestion_predictor.get_hotspot_list() if self.congestion_predictor else []

        tasks_done = self.total_completed - completed_before
        mode = "ML增强" if self.use_ml_predictor else "纯距离"
        congestion = "开" if self.use_congestion_prediction else "关"

        print(f"  当前步数:       {self.step_count}")
        print(f"  测试步数:       {steps}")
        print(f"  耗时:           {elapsed:.3f}秒 ({steps/elapsed:.0f} 步/秒)")
        print(f"  任务完成数:     {tasks_done} (总计: {stats['completed']})")
        print(f"  待处理任务:     {stats['pending']}")
        print(f"  平均等待时间:   {stats['avg_wait_time']}秒")
        print(f"  车辆利用率:     {utilization:.1%}")
        print(f"  拥堵热点数:     {len(hotspots)}")
        print(f"  调度模式:       {mode} | 拥堵预测: {congestion}")
        print(f"  车辆详情:")
        for t in self.trucks:
            print(f"    卡车{t.id}: 状态={t.status}  利用率={t.get_utilization():.1%}  "
                  f"行程数={t.trip_count}")
        print("=" * 60 + "\n")
        return {
            "steps": steps, "elapsed": round(elapsed, 3),
            "steps_per_sec": round(steps / elapsed),
            "tasks_done": tasks_done,
            "total_completed": stats["completed"],
            "pending": stats["pending"],
            "avg_wait": stats["avg_wait_time"],
            "utilization": round(utilization, 3),
            "hotspots": len(hotspots),
            "mode": mode, "congestion": congestion,
            "trucks": [t.to_dict() for t in self.trucks]
        }

    # -----------------------------
    # Helpers
    # -----------------------------
    def find_nearest_node(self, pos):
        best_node = None
        min_dist = float('inf')
        for name, n_pos in self.port.nodes.items():
            d = np.linalg.norm(np.array(n_pos) - pos)
            if d < min_dist:
                min_dist = d
                best_node = name
        return best_node

    def dist(self, a, b):
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    # -----------------------------
    # Hungarian dispatch (upgraded with ML)
    # -----------------------------
    def hungarian_dispatch(self):
        idle_trucks = [t for t in self.trucks if t.status == "IDLE"]
        pending_tasks = [t for t in self.manager.queue if t.status == "PENDING"]

        if len(idle_trucks) == 0 or len(pending_tasks) == 0:
            return {}

        n_trucks = len(idle_trucks)
        n_tasks = len(pending_tasks)
        max_dim = max(n_trucks, n_tasks)
        cost = np.full((max_dim, max_dim), 1e9)

        max_distance = max(
            self.dist((0, 0), (self.port.nodes[t.start][0], self.port.nodes[t.start][1]))
            for t in pending_tasks
        ) if pending_tasks else 200.0

        for i, truck in enumerate(idle_trucks):
            for j, task in enumerate(pending_tasks):
                task_pos = np.array(self.port.nodes[task.start])

                if self.use_ml_predictor and self.task_predictor:
                    context = {
                        "max_distance": max_distance,
                        "waiting_time": time.time() - task.waiting_since,
                        "queue_length": len(pending_tasks)
                    }
                    score = self.task_predictor.predict_score(
                        task, truck.current_pos, task_pos, context
                    )
                    cost[i][j] = -score * 100  # 负号使最大化转最小化
                else:
                    cost[i][j] = self.dist(truck.current_pos, task_pos)

        row_ind, col_ind = linear_sum_assignment(cost)
        assignment = {}
        for r, c in zip(row_ind, col_ind):
            if r < n_trucks and c < n_tasks:
                assignment[idle_trucks[r]] = pending_tasks[c]

        return assignment

    # -----------------------------
    # Collision avoidance
    # -----------------------------
    def _check_collision_risk(self, truck):
        for other in self.trucks:
            if other.id == truck.id:
                continue
            d = np.linalg.norm(truck.current_pos - other.current_pos)
            if d < 4.0 and other.id < truck.id:
                return True
        return False

    # -----------------------------
    # Main logic
    # -----------------------------
    def update_logic(self):
        self.step_count += 1

        # Record truck positions for congestion learning
        truck_positions = [t.current_pos for t in self.trucks]

        if self.congestion_predictor:
            self.congestion_predictor.record_step(truck_positions, self.port.nodes)

        # Auto-generate tasks periodically
        self.auto_task_timer += 1
        if (self.auto_task_timer >= self.auto_task_interval and
                len(self.manager.get_pending_tasks()) < self.max_tasks):
            self.auto_task_timer = 0
            new_tasks = self.gen.create_random_tasks(num=random.randint(1, 2))
            for t in new_tasks:
                t.id = f"T{len(self.manager.queue) + 1:02d}"
            self.manager.queue.extend(new_tasks)

        # 1. Hungarian dispatch (every N steps)
        if self.step_count % self.dispatch_interval == 0:
            assignments = self.hungarian_dispatch()

            for truck, task in assignments.items():
                if task.status == "PENDING":
                    truck.current_task = task
                    truck.status = "PICKING"
                    task.status = "RUNNING"

                    start_node = self.find_nearest_node(truck.current_pos)
                    path = a_star_search(
                        self.port.graph, self.port.nodes,
                        start_node, task.start,
                        truck_positions=truck_positions,
                        congestion_predictor=self.congestion_predictor,
                        congestion_weight=15.0,
                        enable_trend=self.use_congestion_prediction
                    )

                    if path:
                        truck.target_path = [self.port.nodes[n] for n in path[1:]]

        # 2. Truck movement
        for truck in self.trucks:
            truck.record_position()
            truck.update_stats()

            if truck.target_path:
                target = np.array(truck.target_path[0], dtype=np.float64)
                direction = target - truck.current_pos
                dist = np.linalg.norm(direction)

                is_blocked = self._check_collision_risk(truck)

                if not is_blocked:
                    if dist < truck.speed:
                        truck.current_pos = target
                        truck.target_path.pop(0)
                    else:
                        truck.current_pos += (direction / dist) * truck.speed
                else:
                    # Re-plan when blocked (with congestion awareness)
                    if truck.replan_cooldown <= 0 and random.random() < 0.1:
                        start_node = self.find_nearest_node(truck.current_pos)
                        goal = (truck.current_task.end if truck.status == "DELIVERING"
                                else truck.current_task.start)
                        new_path = a_star_search(
                            self.port.graph, self.port.nodes,
                            start_node, goal,
                            truck_positions=truck_positions,
                            congestion_predictor=self.congestion_predictor,
                            congestion_weight=15.0,
                            enable_trend=self.use_congestion_prediction
                        )
                        if new_path:
                            truck.target_path = [self.port.nodes[n] for n in new_path[1:]]
                        truck.replan_cooldown = 5
                    else:
                        truck.replan_cooldown = max(0, truck.replan_cooldown - 1)
            else:
                if truck.status == "PICKING":
                    truck.status = "DELIVERING"
                    path = a_star_search(
                        self.port.graph, self.port.nodes,
                        truck.current_task.start, truck.current_task.end,
                        truck_positions=truck_positions,
                        congestion_predictor=self.congestion_predictor,
                        congestion_weight=15.0,
                        enable_trend=self.use_congestion_prediction
                    )
                    if path:
                        truck.target_path = [self.port.nodes[n] for n in path[1:]]

                elif truck.status == "DELIVERING":
                    if truck.current_task:
                        if self.use_ml_predictor and self.task_predictor:
                            wait_time = time.time() - truck.current_task.waiting_since
                            self.task_predictor.record_outcome(
                                truck.current_task,
                                truck.current_task.priority_score,
                                wait_time,
                                True
                            )
                    self.manager.mark_done(truck.current_task)
                    self.total_completed += 1
                    truck.reset_task()

        # 3. Collect metrics
        self._collect_metrics()

    def _collect_metrics(self):
        if self.step_count % 50 == 0:
            stats = self.manager.get_stats()
            utilization = np.mean([t.get_utilization() for t in self.trucks])
            self.metrics_history.append({
                "step": self.step_count,
                "completed": stats["completed"],
                "pending": stats["pending"],
                "avg_wait": stats["avg_wait_time"],
                "utilization": round(utilization, 3),
                "mode": "ML" if self.use_ml_predictor else "Distance"
            })

    def get_state_dict(self):
        """Return full simulation state for web API / external consumers."""
        return {
            "step": self.step_count,
            "trucks": [t.to_dict() for t in self.trucks],
            "tasks": [t.to_dict() for t in self.manager.queue if t.status != "COMPLETED"],
            "stats": self.manager.get_stats(),
            "utilization": round(np.mean([t.get_utilization() for t in self.trucks]), 3),
            "hotspots": self.congestion_predictor.get_hotspot_list() if self.congestion_predictor else [],
            "heatmap": self.congestion_predictor.get_heatmap_data() if self.congestion_predictor else [],
            "port_nodes": {k: list(v) for k, v in self.port.nodes.items()},
            "port_edges": {k: list(v) for k, v in self.port.graph.items()},
            "mode": "ML" if self.use_ml_predictor else "Distance",
            "metrics_history": self.metrics_history[-20:]
        }

    # -----------------------------
    # Matplotlib visualization
    # -----------------------------
    def run(self):
        if self.headless:
            raise RuntimeError("Cannot run matplotlib mode in headless=True. Use step_once() instead.")

        while plt.fignum_exists(self.fig.number):
            self.update_logic()
            self._render_frame()
            plt.pause(0.02)

    def _render_frame(self):
        self.ax.clear()
        self.port.draw(self.ax)

        # Draw congestion heatmap overlay
        if self.congestion_predictor:
            for h in self.congestion_predictor.get_heatmap_data():
                alpha = min(h["value"] * 0.4, 0.5)
                self.ax.add_patch(plt.Rectangle(
                    (h["x"], h["y"]),
                    self.congestion_predictor.grid_resolution,
                    self.congestion_predictor.grid_resolution,
                    facecolor='red', alpha=alpha, zorder=2
                ))

        # Tasks
        for t in self.manager.queue:
            if t.status == "PENDING":
                p = self.port.nodes[t.start]
                size = 80 + t.urgency * 80
                self.ax.scatter(p[0], p[1], edgecolors='blue',
                                facecolors='none', s=size, alpha=0.6)

        # Trucks
        for truck in self.trucks:
            self.ax.scatter(truck.current_pos[0], truck.current_pos[1],
                            color=truck.color, marker='s', s=200, zorder=6)
            self.ax.text(truck.current_pos[0], truck.current_pos[1] + 1.5,
                         f"T{truck.id}", ha='center', fontsize=8, color=truck.color)

            if truck.target_path:
                pts = [truck.current_pos] + truck.target_path
                xs, ys = zip(*pts)
                self.ax.plot(xs, ys, linestyle=':', alpha=0.5, color=truck.color)

        # Title with stats
        stats = self.manager.get_stats()
        mode = "ML-Enhanced" if self.use_ml_predictor else "Distance-Only"
        title = (f"Port Dispatch System | {mode} | "
                 f"Completed: {stats['completed']} | "
                 f"Pending: {stats['pending']} | "
                 f"Avg Wait: {stats['avg_wait_time']}s | "
                 f"Util: {np.mean([t.get_utilization() for t in self.trucks]):.0%}")
        self.ax.set_title(title, fontsize=11)
        self.ax.set_aspect('equal')

    def step_once(self):
        """Execute one simulation step (for web mode or headless)."""
        self.update_logic()

    def reset(self):
        self.step_count = 0
        self.manager = TaskManager([])
        for truck in self.trucks:
            truck.reset_task()
            truck.current_pos = np.array(self.port.nodes['Gate_In'], dtype=np.float64)

        initial_tasks = self.gen.create_random_tasks(num=5)
        for i, t in enumerate(initial_tasks):
            t.id = f"T{i + 1:02d}"
        self.manager.queue.extend(initial_tasks)

        if self.congestion_predictor:
            self.congestion_predictor = CongestionPredictor()
            self.congestion_predictor.set_node_coords_cache(self.port.nodes)

    def save_models(self):
        if self.task_predictor:
            self.task_predictor.save_model()
        if self.congestion_predictor:
            self.congestion_predictor.save_hotspots()
