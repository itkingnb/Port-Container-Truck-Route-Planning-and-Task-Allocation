import math
import json
import os
from collections import defaultdict


class CongestionPredictor:
    """拥堵热点学习与趋势预测器。

    维护网格化拥堵热力图，使用 EWMA 预测短期拥堵趋势，
    识别高频拥堵热点，使 A* 从即时避障演进为趋势避障。
    """

    def __init__(self, grid_resolution=10.0, ewma_alpha=0.3, hotspot_threshold=0.6):
        self.grid_resolution = grid_resolution
        self.ewma_alpha = ewma_alpha
        self.hotspot_threshold = hotspot_threshold

        # 拥堵热力图: {(grid_x, grid_y): ewma_value}
        self.heatmap = defaultdict(float)
        # 瞬时密度记录: {(grid_x, grid_y): [history_values]}
        self.density_history = defaultdict(list)
        # 高频拥堵热点集合
        self.hotspots = set()
        # 节点级拥堵: {node_name: ewma_value}
        self.node_congestion = defaultdict(float)

        # 统计
        self.step_count = 0
        self.max_history_len = 50

    def _to_grid(self, x, y):
        return (int(x // self.grid_resolution), int(y // self.grid_resolution))

    def record_step(self, truck_positions, node_coords):
        """记录一步仿真中所有车辆位置，更新热力图。"""
        self.step_count += 1
        grid_counts = defaultdict(int)
        node_counts = defaultdict(int)

        # 统计每个网格的车辆数
        for pos in truck_positions:
            gx, gy = self._to_grid(pos[0], pos[1])
            grid_counts[(gx, gy)] += 1

        # 统计每个节点附近的车辆数
        for name, npos in node_coords.items():
            for tpos in truck_positions:
                d = math.sqrt((npos[0] - tpos[0]) ** 2 + (npos[1] - tpos[1]) ** 2)
                if d < 8.0:
                    node_counts[name] += 1

        # EWMA 更新网格热力
        for gkey, count in grid_counts.items():
            density = min(count / 3.0, 1.0)
            old = self.heatmap[gkey]
            self.heatmap[gkey] = self.ewma_alpha * density + (1 - self.ewma_alpha) * old
            self.density_history[gkey].append(density)
            if len(self.density_history[gkey]) > self.max_history_len:
                self.density_history[gkey].pop(0)

        # EWMA 更新节点拥堵
        for name, count in node_counts.items():
            density = min(count / 3.0, 1.0)
            old = self.node_congestion[name]
            self.node_congestion[name] = self.ewma_alpha * density + (1 - self.ewma_alpha) * old

        # 每 20 步刷新热点集合
        if self.step_count % 20 == 0:
            self._update_hotspots()

    def _update_hotspots(self):
        self.hotspots = set()
        for gkey, val in self.heatmap.items():
            if val >= self.hotspot_threshold:
                self.hotspots.add(gkey)

    def get_node_congestion(self, node_name):
        """返回节点的拥堵值 (0~1)，用于 A* 边代价调整。"""
        return self.node_congestion.get(node_name, 0.0)

    def get_grid_congestion(self, x, y):
        """返回网格的拥堵值 (0~1)。"""
        gkey = self._to_grid(x, y)
        return self.heatmap.get(gkey, 0.0)

    def predict_congestion(self, node_name, lookahead_steps=5):
        """基于 EWMA 趋势预测未来拥堵。

        使用近期密度变化率对当前值做线性外推。
        """
        current = self.node_congestion.get(node_name, 0.0)
        gkey = None
        for name, pos in getattr(self, '_node_coords_cache', {}).items():
            if name == node_name:
                gkey = self._to_grid(pos[0], pos[1])
                break

        if gkey is None:
            return current

        history = self.density_history.get(gkey, [])
        if len(history) < 3:
            return current

        recent = history[-5:]
        trend = (recent[-1] - recent[0]) / max(len(recent), 1)
        predicted = current + trend * lookahead_steps
        return max(0.0, min(1.0, predicted))

    def is_hotspot(self, x, y):
        return self._to_grid(x, y) in self.hotspots

    def get_hotspot_list(self):
        return [{"grid": list(g), "value": round(self.heatmap[g], 3)} for g in self.hotspots]

    def get_heatmap_data(self):
        """返回热力图数据供前端渲染。"""
        return [
            {"x": g[0] * self.grid_resolution, "y": g[1] * self.grid_resolution,
             "value": round(v, 3)}
            for g, v in self.heatmap.items() if v > 0.05
        ]

    def save_hotspots(self, path="congestion_hotspots.json"):
        data = {
            "hotspots": [list(g) for g in self.hotspots],
            "heatmap": {str(k): v for k, v in self.heatmap.items()},
            "node_congestion": dict(self.node_congestion)
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_hotspots(self, path="congestion_hotspots.json"):
        if not os.path.exists(path):
            return
        with open(path, "r") as f:
            data = json.load(f)
        self.hotspots = set(tuple(g) for g in data.get("hotspots", []))
        self.heatmap = defaultdict(float, {eval(k): v for k, v in data.get("heatmap", {}).items()})
        self.node_congestion = defaultdict(float, data.get("node_congestion", {}))

    def set_node_coords_cache(self, node_coords):
        self._node_coords_cache = node_coords
