import random
import time


class Task:
    def __init__(self, task_id, task_type, start_node, end_node, urgency=None,
                 deadline=None, created_step=0, waiting_since_step=None):
        self.id = task_id
        self.type = task_type  # 'IMPORT', 'EXPORT', 'TRANSSHIPMENT'
        self.start = start_node
        self.end = end_node
        self.status = "PENDING"  # PENDING, RUNNING, COMPLETED
        self.urgency = urgency if urgency is not None else random.uniform(0.3, 1.0)
        self.deadline = deadline if deadline is not None else time.time() + random.uniform(60, 300)
        self.created_at = time.time()
        self.created_step = created_step
        self.waiting_since_step = created_step if waiting_since_step is None else waiting_since_step
        self.priority_score = 0.0
        self.estimated_distance = 0.0

    def update_waiting_step(self, current_step):
        if self.status == "PENDING":
            self.waiting_since_step = current_step

    def compute_priority(self, distance_cost, max_distance, current_step, waiting_penalty_weight=0.3):
        distance_norm = distance_cost / max(max_distance, 1.0)
        waiting_steps = max(current_step - self.waiting_since_step, 0)
        waiting_norm = min(waiting_steps / 120.0, 1.0)
        self.priority_score = (0.4 * self.urgency + 0.3 * (1.0 - distance_norm) + waiting_penalty_weight * waiting_norm)
        self.estimated_distance = distance_cost
        return self.priority_score

    def to_dict(self, current_step=None):
        waiting_steps = 0 if current_step is None else max(current_step - self.waiting_since_step, 0)
        return {
            "id": self.id, "type": self.type, "start": self.start, "end": self.end,
            "status": self.status, "urgency": self.urgency, "priority_score": self.priority_score,
            "waiting_steps": waiting_steps
        }

    def __repr__(self):
        return (f"[{self.id}] {self.type}: {self.start} -> {self.end} "
                f"({self.status}) urgency={self.urgency:.2f} score={self.priority_score:.2f}")


class TaskGenerator:
    def __init__(self, port):
        self.port = port
        self.quay_nodes = [n for n in port.nodes if n.startswith('Q')]
        self.yard_nodes = [n for n in port.nodes if ('_L' in n or '_R' in n) and not n.endswith('0')]

    def create_random_tasks(self, num=5, current_step=0):
        if not self.quay_nodes or not self.yard_nodes:
            print("Error: insufficient port nodes to generate tasks!")
            return []

        task_list = []
        types = ['IMPORT', 'EXPORT', 'TRANSSHIPMENT']
        type_weights = [0.4, 0.3, 0.3]

        for i in range(num):
            t_type = random.choices(types, weights=type_weights, k=1)[0]
            t_id = f"T{i + 1:03d}"

            if t_type == 'IMPORT':
                s, e = random.choice(self.quay_nodes), random.choice(self.yard_nodes)
            elif t_type == 'EXPORT':
                s, e = 'Gate_In', random.choice(self.yard_nodes)
            else:
                s, e = random.choice(self.yard_nodes), random.choice(self.quay_nodes)

            urgency_bonus = 0.2 if t_type == 'IMPORT' else 0.0
            urgency = min(1.0, random.uniform(0.3, 0.8) + urgency_bonus)
            deadline = time.time() + random.uniform(60, 300)

            task_list.append(Task(
                t_id, t_type, s, e,
                urgency=urgency,
                deadline=deadline,
                created_step=current_step,
                waiting_since_step=current_step
            ))

        return task_list


class TaskManager:
    def __init__(self, tasks):
        self.queue = tasks
        self.completed_tasks = []
        self.task_history = []
        self.total_completed = 0
        self.total_waiting_steps = 0.0

    def get_next_task(self):
        for task in self.queue:
            if task.status == "PENDING":
                task.status = "RUNNING"
                return task
        return None

    def get_pending_tasks(self):
        return [t for t in self.queue if t.status == "PENDING"]

    def mark_done(self, task, current_step):
        task.status = "COMPLETED"
        self.completed_tasks.append(task)
        self.total_completed += 1
        wait_steps = max(current_step - task.waiting_since_step, 0)
        self.total_waiting_steps += wait_steps
        self.task_history.append({
            "id": task.id, "type": task.type, "urgency": task.urgency,
            "wait_steps": wait_steps, "distance": task.estimated_distance
        })

    def get_stats(self):
        avg_wait = self.total_waiting_steps / max(self.total_completed, 1)
        return {
            "completed": self.total_completed,
            "pending": len(self.get_pending_tasks()),
            "avg_wait_steps": round(avg_wait, 2),
            "avg_urgency": round(
                sum(t.urgency for t in self.completed_tasks[-20:]) / max(len(self.completed_tasks[-20:]), 1), 3
            ) if self.completed_tasks else 0
        }
