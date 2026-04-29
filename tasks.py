# tasks.py
import random

class Task:
    def __init__(self, task_id, task_type, start_node, end_node):
        self.id = task_id
        self.type = task_type  # 'IMPORT', 'EXPORT', 'TRANSSHIPMENT'
        self.start = start_node
        self.end = end_node
        self.status = "PENDING" # PENDING, RUNNING, COMPLETED

    def __repr__(self):
        return f"[{self.id}] {self.type}: {self.start} -> {self.end} ({self.status})"

class TaskGenerator:
    def __init__(self, port):
        """
        port: 传入生成的港口实例，用于获取合法的节点列表
        """
        self.port = port
        # 提取泊位节点 (Q1, Q2...)
        self.quay_nodes = [n for n in port.nodes if n.startswith('Q')]
        # 提取堆场内部路口节点 (避免主干道 L0, R0)
        self.yard_nodes = [n for n in port.nodes if ('_L' in n or '_R' in n) and not n.endswith('0')]

    def create_random_tasks(self, num=5):
        if not self.quay_nodes or not self.yard_nodes:
            print("错误：港口节点不足，无法生成任务！")
            return []

        task_list = []
        types = ['IMPORT', 'EXPORT', 'TRANSSHIPMENT']
        
        for i in range(num):
            t_type = random.choice(types)
            t_id = f"T{i+1:03d}"
            
            if t_type == 'IMPORT':
                # 海上 -> 堆场
                s, e = random.choice(self.quay_nodes), random.choice(self.yard_nodes)
            elif t_type == 'EXPORT':
                # 闸口 -> 堆场
                s, e = 'Gate_In', random.choice(self.yard_nodes)
            else: # TRANSSHIPMENT
                # 堆场 -> 泊位
                s, e = random.choice(self.yard_nodes), random.choice(self.quay_nodes)
            
            task_list.append(Task(t_id, t_type, s, e))
        
        return task_list

class TaskManager:
    def __init__(self, tasks):
        self.queue = tasks
        self.completed_tasks = []

    def get_next_task(self):
        for task in self.queue:
            if task.status == "PENDING":
                task.status = "RUNNING"
                return task
        return None

    def mark_done(self, task):
        task.status = "COMPLETED"
        self.completed_tasks.append(task)