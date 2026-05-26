import random
import math
import json
import os
from collections import defaultdict


class RLAgent:
    """Q-Learning 智能体，用于单车决策优化。

    每个 Truck 拥有一个独立的 Agent，基于环境反馈进行策略调整。
    使用离散化状态空间 + Q表（字典），避免深度网络复杂性。
    """

    ACTIONS = {
        0: "accept_nearest",    # 接受最近任务
        1: "accept_highest",    # 接受最高优先级任务
        2: "wait_idle",         # 等待
        3: "relocate_center",   # 前往中心区域待命
    }

    def __init__(self, agent_id, learning_rate=0.1, discount=0.9,
                 epsilon=0.3, epsilon_decay=0.995, epsilon_min=0.05):
        self.id = agent_id
        self.lr = learning_rate
        self.gamma = discount
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min

        # Q表: {state_key: [q0, q1, q2, q3]}
        self.q_table = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])

        # Episode tracking
        self.total_reward = 0.0
        self.episode_count = 0
        self.action_history = []
        self.last_state = None
        self.last_action = None

    def _discretize(self, value, bins, min_val, max_val):
        clamped = max(min_val, min(max_val, value))
        norm = (clamped - min_val) / max(max_val - min_val, 1e-6)
        return min(int(norm * bins), bins - 1)

    def get_state(self, truck, port_nodes, task_manager):
        """将连续状态离散化为状态键。

        状态空间: [has_task, nearby_vehicles_bin, nearest_task_dist_bin, queue_length_bin]
        """
        has_task = 1 if truck.current_task is not None else 0

        # 周围车辆数（3 档）
        nearby = truck.rl_state.get("nearby_vehicles", 0)
        nb_bin = self._discretize(nearby, 3, 0, 6)

        # 最近待处理任务距离（5 档）
        pending = task_manager.get_pending_tasks()
        nearest = float('inf')
        for t in pending:
            tpos = port_nodes.get(t.start, (0, 0))
            d = math.sqrt((truck.current_pos[0] - tpos[0]) ** 2 +
                          (truck.current_pos[1] - tpos[1]) ** 2)
            nearest = min(nearest, d)
        nearest = min(nearest, 300.0)
        dist_bin = self._discretize(nearest, 5, 0, 300)

        # 队列长度（3 档）
        qlen = len(pending)
        qlen_bin = self._discretize(qlen, 3, 0, 15)

        return f"{has_task}_{nb_bin}_{dist_bin}_{qlen_bin}"

    def choose_action(self, state_key, explore=True):
        """epsilon-greedy 动作选择。"""
        q_values = self.q_table[state_key]

        if explore and random.random() < self.epsilon:
            action = random.randrange(len(self.ACTIONS))
        else:
            max_q = max(q_values)
            best_actions = [i for i, q in enumerate(q_values) if q == max_q]
            action = random.choice(best_actions)

        self.last_state = state_key
        self.last_action = action
        return action

    def learn(self, state_key, action, reward, next_state_key):
        """Q-Learning 更新。"""
        current_q = self.q_table[state_key][action]
        max_next_q = max(self.q_table[next_state_key])
        new_q = current_q + self.lr * (reward + self.gamma * max_next_q - current_q)
        self.q_table[state_key][action] = new_q
        self.total_reward += reward

    def decay_epsilon(self):
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def end_episode(self):
        self.episode_count += 1
        self.decay_epsilon()
        self.total_reward = 0.0

    def save(self, path=None):
        if path is None:
            path = f"rl_agent_{self.id}.json"
        data = {
            "id": self.id, "epsilon": self.epsilon,
            "q_table": {k: list(v) for k, v in self.q_table.items()},
            "episodes": self.episode_count
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path=None):
        if path is None:
            path = f"rl_agent_{self.id}.json"
        if not os.path.exists(path):
            return
        with open(path, "r") as f:
            data = json.load(f)
        self.epsilon = data.get("epsilon", self.epsilon)
        self.episode_count = data.get("episodes", 0)
        for k, v in data.get("q_table", {}).items():
            self.q_table[k] = v


class MultiAgentCoordinator:
    """多智能体协调器，管理所有 RL Agent 并处理冲突消解。"""

    def __init__(self, num_agents, learning_rate=0.1, discount=0.9, epsilon=0.3):
        self.agents = {}
        for i in range(num_agents):
            self.agents[i + 1] = RLAgent(
                agent_id=i + 1,
                learning_rate=learning_rate,
                discount=discount,
                epsilon=epsilon
            )
        # 协作奖励追踪
        self.collaboration_bonus = 0.0
        self.conflict_count = 0
        self.step_count = 0

    def get_agent(self, agent_id):
        return self.agents.get(agent_id)

    def coordinate_actions(self, truck_actions, trucks, port_nodes, task_manager):
        """多智能体动作协调，消解冲突。

        如果两辆车选择了同一个任务，高 Q 值车获得任务，另一辆重新选择。
        """
        resolved = {}
        task_assignments = {}

        for truck_id, (action, q_value) in truck_actions.items():
            if action in (0, 1):  # 需要接受任务
                agent = self.agents[truck_id]
                state = agent.last_state
                pending = task_manager.get_pending_tasks()

                if pending:
                    if action == 0:  # accept_nearest
                        truck = next(t for t in trucks if t.id == truck_id)
                        best_task = min(pending,
                                        key=lambda t: math.sqrt(
                                            (truck.current_pos[0] - port_nodes[t.start][0]) ** 2 +
                                            (truck.current_pos[1] - port_nodes[t.start][1]) ** 2))
                    else:  # accept_highest
                        best_task = max(pending, key=lambda t: t.priority_score)

                    if best_task.id in task_assignments:
                        other_truck, other_q = task_assignments[best_task.id]
                        if q_value > other_q:
                            task_assignments[best_task.id] = (truck_id, q_value)
                            resolved[truck_id] = ("accept", best_task)
                            resolved[other_truck] = ("wait", None)
                            self.conflict_count += 1
                        else:
                            resolved[truck_id] = ("wait", None)
                    else:
                        task_assignments[best_task.id] = (truck_id, q_value)
                        resolved[truck_id] = ("accept", best_task)
                else:
                    resolved[truck_id] = ("wait", None)
            elif action == 3:  # relocate
                resolved[truck_id] = ("relocate", None)
            else:  # wait
                resolved[truck_id] = ("wait", None)

        self.step_count += 1
        return resolved

    def compute_reward(self, truck, action_result, was_completed,
                       had_collision_risk, idle_duration):
        """计算奖励信号。"""
        reward = 0.0
        if was_completed:
            reward += 10.0
        if had_collision_risk:
            reward -= 5.0
        if truck.status == "IDLE":
            reward -= 0.05 * min(idle_duration, 50)
        if action_result == "relocate":
            reward -= 0.5
        return reward

    def save_all(self, directory="."):
        for agent in self.agents.values():
            agent.save(os.path.join(directory, f"rl_agent_{agent.id}.json"))

    def load_all(self, directory="."):
        for agent in self.agents.values():
            agent.load(os.path.join(directory, f"rl_agent_{agent.id}.json"))

    def get_stats(self):
        total_episodes = sum(a.episode_count for a in self.agents.values())
        avg_epsilon = sum(a.epsilon for a in self.agents.values()) / max(len(self.agents), 1)
        return {
            "total_episodes": total_episodes,
            "avg_epsilon": round(avg_epsilon, 3),
            "conflicts_resolved": self.conflict_count
        }
