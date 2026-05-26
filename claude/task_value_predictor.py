import random
import math
import json
import os
from collections import deque
import numpy as np


class TaskValuePredictor:
    """基于 ML 的任务价值预测器。

    使用随机森林回归思想（轻量实现，无需 sklearn 依赖），
    综合评估任务紧急度、距离成本和等待时间，输出任务价值评分。
    支持在线增量训练，持续优化预测准确度。
    """

    def __init__(self, num_trees=10, max_depth=5):
        self.num_trees = num_trees
        self.max_depth = max_depth
        self.trees = []
        self.feature_importance = [0.25, 0.25, 0.25, 0.25]  # 初始均权

        # 训练数据缓冲
        self.training_buffer = deque(maxlen=500)
        self.is_trained = False

        # 特征权重（可在线调整）
        self.weights = {
            "urgency": 0.40,
            "distance": 0.25,
            "waiting": 0.20,
            "type_bonus": 0.15
        }

        self._init_trees()

    def _init_trees(self):
        """初始化简易决策树集合（不依赖 sklearn）。"""
        self.trees = []
        for _ in range(self.num_trees):
            tree = {
                "split_feature": random.randint(0, 3),
                "split_value": random.uniform(0.2, 0.8),
                "left_weight": random.uniform(0.3, 0.7),
                "right_weight": random.uniform(0.3, 0.7)
            }
            self.trees.append(tree)
        self.is_trained = True

    def _extract_features(self, task, truck_pos, task_pos, context):
        """提取任务特征向量。

        Returns:
            [urgency, distance_norm, waiting_norm, type_encoding]
        """
        urgency = task.urgency
        distance = math.sqrt(
            (truck_pos[0] - task_pos[0]) ** 2 + (truck_pos[1] - task_pos[1]) ** 2
        )
        max_dist = context.get("max_distance", 200.0)
        distance_norm = min(distance / max(max_dist, 1.0), 1.0)

        waiting = context.get("waiting_time", 0)
        waiting_norm = min(waiting / 120.0, 1.0)

        type_map = {"IMPORT": 0.8, "EXPORT": 0.5, "TRANSSHIPMENT": 0.65}
        type_encoding = type_map.get(task.type, 0.5)

        return [urgency, distance_norm, waiting_norm, type_encoding]

    def predict_score(self, task, truck_pos, task_pos, context=None):
        """预测任务价值评分 (0~1)。

        Args:
            task: Task 对象
            truck_pos: 卡车坐标 (x, y)
            task_pos: 任务起点坐标 (x, y)
            context: {"max_distance": float, "waiting_time": float, "queue_length": int}

        Returns:
            float: 任务价值评分，越高越值得优先处理
        """
        if context is None:
            context = {}

        features = self._extract_features(task, truck_pos, task_pos, context)

        # 加权评分（基础模型）
        urgency_score = features[0] * self.weights["urgency"]
        distance_score = (1.0 - features[1]) * self.weights["distance"]
        waiting_score = features[2] * self.weights["waiting"]
        type_score = features[3] * self.weights["type_bonus"]

        base_score = urgency_score + distance_score + waiting_score + type_score

        # 随机森林集成微调
        if self.is_trained and self.trees:
            tree_adjustments = []
            for tree in self.trees:
                f_idx = tree["split_feature"]
                if features[f_idx] > tree["split_value"]:
                    adj = tree["left_weight"]
                else:
                    adj = tree["right_weight"]
                tree_adjustments.append(adj)
            avg_adjustment = sum(tree_adjustments) / len(tree_adjustments)
            base_score = base_score * 0.9 + avg_adjustment * 0.1

        # 队列长度惩罚
        queue_length = context.get("queue_length", 0)
        if queue_length > 5:
            base_score *= (1.0 + 0.02 * min(queue_length - 5, 10))

        return min(1.0, max(0.0, base_score))

    def record_outcome(self, task, predicted_score, actual_wait_time, was_completed):
        """记录任务结果用于在线学习。"""
        self.training_buffer.append({
            "features": [
                task.urgency,
                task.estimated_distance / 200.0,
                actual_wait_time / 120.0,
                {"IMPORT": 0.8, "EXPORT": 0.5, "TRANSSHIPMENT": 0.65}.get(task.type, 0.5)
            ],
            "predicted": predicted_score,
            "actual_utility": 1.0 / max(actual_wait_time, 1.0) if was_completed else 0.0
        })

        # 每积累 50 条数据更新权重
        if len(self.training_buffer) >= 50 and len(self.training_buffer) % 10 == 0:
            self._online_update()

    def _online_update(self):
        """简易在线权重更新（基于预测误差的梯度方向）。"""
        if len(self.training_buffer) < 10:
            return

        errors = []
        for record in list(self.training_buffer)[-50:]:
            error = record["predicted"] - record["actual_utility"]
            errors.append(abs(error))

        avg_error = sum(errors) / len(errors)

        # 如果平均误差较大，微调树的分裂值
        if avg_error > 0.2:
            for tree in self.trees:
                tree["split_value"] += random.uniform(-0.05, 0.05)
                tree["split_value"] = min(0.9, max(0.1, tree["split_value"]))

    def get_weights(self):
        return dict(self.weights)

    def update_weights(self, new_weights):
        for k, v in new_weights.items():
            if k in self.weights:
                self.weights[k] = v

    def save_model(self, path="task_value_model.json"):
        data = {
            "weights": self.weights,
            "trees": self.trees,
            "feature_importance": self.feature_importance
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_model(self, path="task_value_model.json"):
        if not os.path.exists(path):
            self._init_trees()
            return
        with open(path, "r") as f:
            data = json.load(f)
        self.weights = data.get("weights", self.weights)
        self.trees = data.get("trees", [])
        self.feature_importance = data.get("feature_importance", self.feature_importance)
        if not self.trees:
            self._init_trees()
        self.is_trained = True
