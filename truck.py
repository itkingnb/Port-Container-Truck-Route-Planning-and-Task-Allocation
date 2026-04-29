import numpy as np
class Truck:
    def __init__(self, truck_id, start_pos, color):
        self.id = truck_id
        self.current_pos = np.array(start_pos, dtype=np.float64)
        self.color = color
        self.target_path = []  # 存放坐标点列表 [(x,y), (x,y)...]
        self.status = "IDLE"   # 状态: IDLE, PICKING, DELIVERING
        self.current_task = None
        self.speed = 3       # 移动速度
        self.replan_cooldown = 0  # 新增：重规划冷却