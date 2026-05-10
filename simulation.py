import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from draw_port import AdvancedRealisticPort
from tasks import TaskGenerator, TaskManager
from truck import Truck
from path_planning import a_star_search
import numpy as np
import random
from scipy.optimize import linear_sum_assignment
import math


class PortSimApp:
    def __init__(self, num_trucks=3):
        # 初始化地图和任务管理
        self.port = AdvancedRealisticPort(seed=42)
        self.port.generate(num_cols=8, num_rows=3, yard_prob=0.7)
        self.gen = TaskGenerator(self.port)
        self.manager = TaskManager([])

        # 初始化卡车
        self.trucks = []
        colors = ['red', 'blue', 'green', 'purple', 'darkorange']
        start_node_pos = self.port.nodes['Gate_In']

        for i in range(num_trucks):
            t = Truck(i + 1,
                      np.array(start_node_pos, dtype=np.float64),
                      colors[i % len(colors)])
            self.trucks.append(t)

        # 图形界面
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        plt.subplots_adjust(bottom=0.2)

        ax_btn = plt.axes([0.4, 0.05, 0.2, 0.05])
        self.btn_add = Button(ax_btn, '新增一个随机任务',
                              color='lightgray', hovercolor='skyblue')
        self.btn_add.on_clicked(self._on_add_task)

    # -----------------------------
    # 任务生成
    # -----------------------------
    def _on_add_task(self, event):
        new_task = self.gen.create_random_tasks(num=1)[0]
        new_task.id = f"T{len(self.manager.queue) + 1:02d}"
        self.manager.queue.append(new_task)
        print(f"系统接收新任务: {new_task}")

    # -----------------------------
    # 最近节点
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

    # -----------------------------
    # 欧几里得距离
    # -----------------------------
    def dist(self, a, b):
        return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)

    # -----------------------------
    # ⭐ 匈牙利算法任务分配
    # -----------------------------
    def hungarian_dispatch(self):
        idle_trucks = [t for t in self.trucks if t.status == "IDLE"]
        pending_tasks = [t for t in self.manager.queue if t.status == "PENDING"]

        if len(idle_trucks) == 0 or len(pending_tasks) == 0:
            return {}

        cost = np.zeros((len(idle_trucks), len(pending_tasks)))

        for i, truck in enumerate(idle_trucks):
            for j, task in enumerate(pending_tasks):
                truck_pos = truck.current_pos
                task_pos = np.array(self.port.nodes[task.start])

                # 距离成本
                d = self.dist(truck_pos, task_pos)

                # 可扩展：任务惩罚（当前简单版本）
                cost[i][j] = d

        row_ind, col_ind = linear_sum_assignment(cost)

        assignment = {}
        for r, c in zip(row_ind, col_ind):
            assignment[idle_trucks[r]] = pending_tasks[c]

        return assignment

    # -----------------------------
    # 主逻辑
    # -----------------------------
    def update_logic(self):

        # ⭐ 1. 匈牙利任务分配（核心替换点）
        assignments = self.hungarian_dispatch()

        for truck, task in assignments.items():
            if task.status == "PENDING":
                truck.current_task = task
                truck.status = "PICKING"
                task.status = "RUNNING"

                start_node = self.find_nearest_node(truck.current_pos)

                path = a_star_search(
                    self.port.graph,
                    self.port.nodes,
                    start_node,
                    task.start
                )

                if path:
                    truck.target_path = [
                        self.port.nodes[n] for n in path[1:]
                    ]

        # ⭐ 2. 车辆运动逻辑（保持你原来的）
        for truck in self.trucks:

            if truck.target_path:

                target = np.array(truck.target_path[0], dtype=np.float64)
                direction = target - truck.current_pos
                dist = np.linalg.norm(direction)

                higher_priority_pos = [
                    self.trucks[i].current_pos
                    for i in range(len(self.trucks))
                    if self.trucks[i].id < truck.id
                ]

                is_blocked = False
                for pos in higher_priority_pos:
                    if np.linalg.norm(truck.current_pos - pos) < 4.0:
                        is_blocked = True
                        break

                if not is_blocked:
                    if dist < truck.speed:
                        truck.current_pos = target
                        truck.target_path.pop(0)
                    else:
                        truck.current_pos += (direction / dist) * truck.speed

                else:
                    if random.random() < 0.05:
                        start_node = self.find_nearest_node(truck.current_pos)
                        goal = truck.current_task.end if truck.status == "DELIVERING" else truck.current_task.start

                        new_path = a_star_search(
                            self.port.graph,
                            self.port.nodes,
                            start_node,
                            goal
                        )

                        if new_path:
                            truck.target_path = [
                                self.port.nodes[n] for n in new_path[1:]
                            ]

            else:
                if truck.status == "PICKING":
                    truck.status = "DELIVERING"

                    path = a_star_search(
                        self.port.graph,
                        self.port.nodes,
                        truck.current_task.start,
                        truck.current_task.end
                    )

                    if path:
                        truck.target_path = [
                            self.port.nodes[n] for n in path[1:]
                        ]

                elif truck.status == "DELIVERING":
                    print(f"卡车 {truck.id} 完成任务")
                    truck.status = "IDLE"
                    truck.current_task = None

    # -----------------------------
    # 可视化
    # -----------------------------
    def run(self):

        while plt.fignum_exists(self.fig.number):

            self.update_logic()

            self.ax.clear()
            self.port.draw(self.ax)

            # 任务点
            for t in self.manager.queue:
                if t.status == "PENDING":
                    p = self.port.nodes[t.start]
                    self.ax.scatter(p[0], p[1],
                                    edgecolors='blue',
                                    facecolors='none',
                                    s=100,
                                    alpha=0.5)

            # 卡车
            for truck in self.trucks:
                self.ax.scatter(truck.current_pos[0],
                                truck.current_pos[1],
                                color=truck.color,
                                marker='s',
                                s=180)

                self.ax.text(truck.current_pos[0],
                             truck.current_pos[1]+1.5,
                             f"Truck {truck.id}",
                             ha='center',
                             fontsize=8,
                             color=truck.color)

                if truck.target_path:
                    pts = [truck.current_pos] + truck.target_path
                    xs, ys = zip(*pts)
                    self.ax.plot(xs, ys,
                                 linestyle=':',
                                 alpha=0.6,
                                 color=truck.color)

            pending = len([t for t in self.manager.queue if t.status == "PENDING"])
            self.ax.set_title(f"港口调度系统 | 待处理任务: {pending} | 匈牙利分配 + A*路径规划")

            plt.pause(0.01)