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
                 use_ml_predictor=True, use_congestion_prediction=True):
        # 港口
        self.port = AdvancedRealisticPort(seed=42)
        self.port.generate(num_cols=port_cols, num_rows=port_rows, yard_prob=0.7)
        self.gen = TaskGenerator(self.port)
        self.manager = TaskManager([])

        # 智能化模块
        self.use_ml_predictor = use_ml_predictor
        self.use_congestion_prediction = use_congestion_prediction
        self.task_predictor = TaskValuePredictor() if use_ml_predictor else None
        self.congestion_predictor = CongestionPredictor() if use_congestion_prediction else None

        if self.congestion_predictor:
            self.congestion_predictor.set_node_coords_cache(self.port.nodes)

        # 卡车
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

        # 仿真状态
        self.step_count = 0
        self.dispatch_interval = 3
        self.auto_task_timer = 0
        self.auto_task_interval = 15
        self.max_tasks = 20
        self.running = True

        # 统计
        self.total_completed = 0
        self.total_wait_time = 0.0
        self.start_time = time.time()
        self.metrics_history = []

        # 初始任务
        initial_tasks = self.gen.create_random_tasks(num=5)
        for i, t in enumerate(initial_tasks):
            t.id = f"T{i + 1:02d}"
        self.manager.queue.extend(initial_tasks)

    # -----------------------------
    # 辅助方法
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
    # 匈牙利任务分配 (ML增强)
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
                    cost[i][j] = -score * 100
                else:
                    cost[i][j] = self.dist(truck.current_pos, task_pos)

        row_ind, col_ind = linear_sum_assignment(cost)
        assignment = {}
        for r, c in zip(row_ind, col_ind):
            if r < n_trucks and c < n_tasks:
                assignment[idle_trucks[r]] = pending_tasks[c]

        return assignment

    # -----------------------------
    # 碰撞检测
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
    # 主逻辑
    # -----------------------------
    def update_logic(self):
        self.step_count += 1

        truck_positions = [t.current_pos for t in self.trucks]

        if self.congestion_predictor:
            self.congestion_predictor.record_step(truck_positions, self.port.nodes)

        # 自动生成任务
        self.auto_task_timer += 1
        if (self.auto_task_timer >= self.auto_task_interval and
                len(self.manager.get_pending_tasks()) < self.max_tasks):
            self.auto_task_timer = 0
            new_tasks = self.gen.create_random_tasks(num=random.randint(1, 2))
            for t in new_tasks:
                t.id = f"T{len(self.manager.queue) + 1:02d}"
            self.manager.queue.extend(new_tasks)

        # 匈牙利分配
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

        # 车辆运动
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

    # -----------------------------
    # 外部接口
    # -----------------------------
    def step_once(self):
        """执行一步仿真（供 Web API 调用）。"""
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

    def run_benchmark(self, steps=200):
        """运行性能测试，输出格式化结果。"""
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

    def get_state_dict(self):
        """返回完整仿真状态（供 Web API 和外部消费）。"""
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

    def save_models(self):
        if self.task_predictor:
            self.task_predictor.save_model()
        if self.congestion_predictor:
            self.congestion_predictor.save_hotspots()
