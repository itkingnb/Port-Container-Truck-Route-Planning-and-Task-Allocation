# path_planning.py
import heapq
import math

def heuristic(pos1, pos2):
    # 使用欧几里得距离作为启发式函数 (h值)
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

def a_star_search(graph, node_coords, start, end, truck_positions=None):
    """
    graph: 邻接表 {u: [v1, v2...]}
    node_coords: 坐标字典 {node: (x, y)}
    start: 起点节点名
    end: 终点节点名
    """
    # 优先队列，存储 (f_score, current_node)
    open_set = []
    heapq.heappush(open_set, (0, start))
    
    # 记录从起点到当前节点的实际代价 (g_score)
    g_score = {node: float('inf') for node in node_coords}
    g_score[start] = 0
    
    # 记录路径：came_from[v] = u 表示是从 u 走到 v 的
    came_from = {}
    
    while open_set:
        # 取出 f_score 最小的节点
        current_f, current = heapq.heappop(open_set)
        
        if current == end:
            # 找到终点，回溯路径
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            return path[::-1] # 返回正向路径
        
        # 遍历邻居
        for neighbor in graph.get(current, []):
            dist = heuristic(node_coords[current], node_coords[neighbor])
            
            # --- 新增：动态拥堵惩罚 ---
            congestion_penalty = 0
            if truck_positions:
                for t_pos in truck_positions:
                    # 如果邻居节点附近有其他卡车，大幅增加这条边的代价
                    d_to_truck = heuristic(node_coords[neighbor], t_pos)
                    if d_to_truck < 5.0:  # 5.0 是感应半径
                        congestion_penalty += 50.0 # 惩罚值，让它倾向于绕路
            
            tentative_g = g_score[current] + dist + congestion_penalty
            
            if tentative_g < g_score[neighbor]:
                # 发现更优路径
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic(node_coords[neighbor], node_coords[end])
                heapq.heappush(open_set, (f_score, neighbor))
                
    return None # 没找到路径