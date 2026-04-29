import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from draw_port import AdvancedRealisticPort
from tasks import TaskGenerator, TaskManager
from truck import Truck
from path_planning import a_star_search
import numpy as np
import random
class PortSimApp:
    def __init__(self, num_trucks=3):
        # 初始化地图和任务管理
        self.port = AdvancedRealisticPort(seed=42)
        self.port.generate(num_cols=8, num_rows=3, yard_prob=0.7)
        self.gen = TaskGenerator(self.port)
        self.manager = TaskManager([])

        # 初始化多辆卡车
        self.trucks = []
        colors = ['red', 'blue', 'green', 'purple', 'darkorange']
        start_node_pos = self.port.nodes['Gate_In']
        
        for i in range(num_trucks):
            # 确保传入坐标为 np.array
            t = Truck(i+1, np.array(start_node_pos, dtype=np.float64), colors[i % len(colors)])
            self.trucks.append(t)

        # 创建画布
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        plt.subplots_adjust(bottom=0.2)
        
        # UI 按钮
        ax_btn = plt.axes([0.4, 0.05, 0.2, 0.05])
        self.btn_add = Button(ax_btn, '新增一个随机任务', color='lightgray', hovercolor='skyblue')
        self.btn_add.on_clicked(self._on_add_task)

    def _on_add_task(self, event):
        new_task = self.gen.create_random_tasks(num=1)[0]
        new_task.id = f"T{len(self.manager.queue) + 1:02d}"
        self.manager.queue.append(new_task)
        print(f"系统接收新任务: {new_task}")

    def find_nearest_node(self, pos):
        """寻找距离当前坐标最近的节点名称"""
        best_node = None
        min_dist = float('inf')
        for name, n_pos in self.port.nodes.items():
            d = np.linalg.norm(np.array(n_pos) - pos)
            if d < min_dist:
                min_dist = d
                best_node = name
        return best_node

    def update_logic(self):
        all_truck_pos = [t.current_pos for t in self.trucks]

        for truck in self.trucks:
            # 1. 任务领取 (保持不变)
            if truck.status == "IDLE":
                task = self.manager.get_next_task()
                if task:
                    truck.current_task = task
                    truck.status = "PICKING"
                    start_node = self.find_nearest_node(truck.current_pos)
                    path = a_star_search(self.port.graph, self.port.nodes, start_node, task.start)
                    if path:
                        truck.target_path = [self.port.nodes[n] for n in path[1:]]
                continue

            # 2. 移动与智能避让
            if truck.target_path:
                target = np.array(truck.target_path[0], dtype=np.float64)
                direction = target - truck.current_pos
                dist = np.linalg.norm(direction)
                
                # 获取【比自己优先级高】的卡车位置 (即 ID 比自己小的车)
                # 这样 Truck 1 永远不会因为 Truck 2 而停下，打破死锁
                higher_priority_pos = [self.trucks[i].current_pos for i in range(len(self.trucks)) 
                                     if self.trucks[i].id < truck.id]
                
                is_blocked = False
                for pos in higher_priority_pos:
                    if np.linalg.norm(truck.current_pos - pos) < 4.0: # 安全车距
                        is_blocked = True
                        break
                
                if not is_blocked:
                    # 只有没被堵住才移动
                    if dist < truck.speed:
                        truck.current_pos = target
                        truck.target_path.pop(0)
                    else:
                        truck.current_pos += (direction / dist) * truck.speed
                else:
                    # 被堵住了：原地等待，或者尝试绕路
                    # 只有在堵住很久的时候才重新规划，避免计算量过载
                    if random.random() < 0.05: # 5% 的概率尝试重新找路绕开高优先级车
                        start_node = self.find_nearest_node(truck.current_pos)
                        goal = truck.current_task.end if truck.status == "DELIVERING" else truck.current_task.start
                        new_path = a_star_search(self.port.graph, self.port.nodes, start_node, goal, 
                                               truck_positions=higher_priority_pos)
                        if new_path:
                            truck.target_path = [self.port.nodes[n] for n in new_path[1:]]

            # 3. 状态转换
            else:
                if truck.status == "PICKING":
                    truck.status = "DELIVERING"
                    path = a_star_search(self.port.graph, self.port.nodes, 
                                       truck.current_task.start, truck.current_task.end)
                    if path:
                        truck.target_path = [self.port.nodes[n] for n in path[1:]]
                elif truck.status == "DELIVERING":
                    print(f"卡车 {truck.id} 完成任务")
                    truck.status = "IDLE"
                    truck.current_task = None

    def run(self):
        """主循环"""
        while plt.fignum_exists(self.fig.number):
            self.update_logic()
            
            # 绘图渲染
            self.ax.clear()
            self.port.draw(self.ax)
            
            # 画出待分配任务
            for t in self.manager.queue:
                if t.status == "PENDING":
                    p = self.port.nodes[t.start]
                    self.ax.scatter(p[0], p[1], edgecolors='blue', facecolors='none', s=100, alpha=0.5)

            # 画出卡车
            for truck in self.trucks:
                t_color = truck.color 
                # 绘制卡车
                self.ax.scatter(truck.current_pos[0], truck.current_pos[1], 
                                color=t_color, marker='s', s=180, zorder=20)
                # 绘制编号
                self.ax.text(truck.current_pos[0], truck.current_pos[1]+1.5, f"Truck {truck.id}", 
                             ha='center', fontsize=8, color=t_color, fontweight='bold')
                
                # 绘制路径虚线
                if truck.target_path:
                    pts = [truck.current_pos] + truck.target_path
                    xs, ys = zip(*pts)
                    self.ax.plot(xs, ys, color=t_color, linestyle=':', alpha=0.6, lw=1.5)

            active_tasks = len([t for t in self.manager.queue if t.status == "PENDING"])
            self.ax.set_title(f"港口智能调度系统 | 待处理任务: {active_tasks} | 避障模式: 开启")
            
            plt.pause(0.01)