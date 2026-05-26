import numpy as np
from collections import deque


class Truck:
    def __init__(self, truck_id, start_pos, color):
        self.id = truck_id
        self.current_pos = np.array(start_pos, dtype=np.float64)
        self.color = color
        self.target_path = []
        self.status = "IDLE"  # IDLE, PICKING, DELIVERING, WAITING
        self.current_task = None
        self.speed = 3
        self.replan_cooldown = 0

        # RL state
        self.rl_state = {
            "has_task": False,
            "nearby_vehicles": 0,
            "nearest_task_dist": float("inf"),
            "current_node": None
        }
        self.last_action = None
        self.last_reward = 0.0

        # History trajectory for congestion analysis
        self.trajectory = deque(maxlen=200)
        self.trip_count = 0
        self.total_distance = 0.0
        self.idle_steps = 0
        self.busy_steps = 0

    def record_position(self):
        self.trajectory.append(tuple(self.current_pos))

    def update_stats(self):
        if self.status == "IDLE":
            self.idle_steps += 1
        else:
            self.busy_steps += 1

    def get_utilization(self):
        total = self.idle_steps + self.busy_steps
        return self.busy_steps / max(total, 1)

    def reset_task(self):
        if self.current_task:
            self.trip_count += 1
        self.current_task = None
        self.status = "IDLE"
        self.target_path = []

    def to_dict(self):
        return {
            "id": self.id,
            "pos": [round(self.current_pos[0], 1), round(self.current_pos[1], 1)],
            "status": self.status,
            "color": self.color,
            "task_id": self.current_task.id if self.current_task else None,
            "utilization": round(self.get_utilization(), 2),
            "trip_count": self.trip_count
        }
