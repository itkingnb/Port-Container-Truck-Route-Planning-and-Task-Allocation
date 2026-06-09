import heapq
import math
from functools import lru_cache
from congestion_predictor import *

def heuristic(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2)


def a_star_search(graph, node_coords, start, end, truck_positions=None,congestion_predictor=None,congestion_weight=15.0,enable_trend=True):
    """增强 A* 路径搜索，集成拥堵预测机制。

    Args:
        graph: 邻接表 {u: [v1, v2...]}
        node_coords: 坐标字典 {node: (x, y)}
        start: 起点节点名
        end: 终点节点名
        truck_positions: 当前所有卡车位置列表，用于即时避障
        congestion_predictor: CongestionPredictor 实例，用于趋势预测
        congestion_weight: 拥堵惩罚权重
        enable_trend: 是否启用趋势预测（False 时退化为即时避障）

    Returns:
        路径节点名列表，或 None
    """
    if start not in graph or end not in node_coords:
        return None

    open_set = []
    heapq.heappush(open_set, (0, start))

    g_score = {node: float('inf') for node in node_coords}
    g_score[start] = 0

    came_from = {}
    visited = set()

    while open_set:
        current_f, current = heapq.heappop(open_set)

        if current in visited:
            continue
        visited.add(current)

        if current == end:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            return path[::-1]

        for neighbor in graph.get(current, []):
            if neighbor in visited:
                continue

            dist = heuristic(node_coords[current], node_coords[neighbor])

            # 即时拥堵惩罚（基于当前卡车位置）
            instant_penalty = 0
            if truck_positions:
                for t_pos in truck_positions:
                    d_to_truck = heuristic(node_coords[neighbor], t_pos)
                    if d_to_truck < 6.0:
                        instant_penalty += 40.0 * (1.0 - d_to_truck / 6.0)

            # 趋势拥堵惩罚（基于历史学习）
            trend_penalty = 0
            if congestion_predictor and enable_trend:
                base_cong = congestion_predictor.get_node_congestion(neighbor)
                if congestion_predictor.is_hotspot(
                        node_coords[neighbor][0], node_coords[neighbor][1]):
                    base_cong = max(base_cong, 0.7)
                if base_cong > 0.1:
                    predicted = congestion_predictor.predict_congestion(neighbor)
                    trend_penalty = congestion_weight * max(base_cong, predicted)

            tentative_g = g_score[current] + dist + instant_penalty + trend_penalty

            if tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic(node_coords[neighbor], node_coords[end])
                heapq.heappush(open_set, (f_score, neighbor))

    return None


@lru_cache(maxsize=512)
def _cached_heuristic(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def a_star_search_cached(graph, node_coords, start, end, truck_positions=None,congestion_predictor=None, congestion_weight=15.0):               
    """带缓存的 A* 版本，适合大规模场景。"""
    return a_star_search(
        graph, node_coords, start, end,
        truck_positions=truck_positions,
        congestion_predictor=congestion_predictor,
        congestion_weight=congestion_weight,
        enable_trend=True
    )
