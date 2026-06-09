import random
import math


class AdvancedRealisticPort:
    """港口布局生成器。从 8x3 到 20x10 的港口场景。"""
    
    def __init__(self, seed=None):
        if seed is not None:
            random.seed(seed)
        self.nodes = {}
        self.graph = {}
        self.yards = []
        self.zones = []
        self.node_registry = set()

        # Configurable layout parameters
        self.col_spacing = 18
        self.row_spacing = 12
        self.base_y = 10

    def generate(self, num_cols=8, num_rows=3, yard_prob=0.7, quay_prob=0.6):
        self.nodes = {}
        self.graph = {}
        self.yards = []
        self.zones = []
        self.node_registry = set()

        # 动态间距
        if num_cols > 12:
            self.col_spacing = 14
            self.row_spacing = 10
        elif num_cols > 16:
            self.col_spacing = 12
            self.row_spacing = 9
        else:
            self.col_spacing = 18
            self.row_spacing = 12

        # 出入口
        self._add_node('Gate_In', (0, self.base_y))
        self._add_node('Gate_Out', (num_cols * self.col_spacing + 10, self.base_y))

        prev_column_nodes = []

        for c in range(1, num_cols + 1):
            x_left = c * self.col_spacing - 5
            x_right = c * self.col_spacing + 5
            q_node = f'Q{c}'
            self._add_node(q_node, ((x_left + x_right) / 2, 2))
            if random.random() < quay_prob:
                self.zones.append({
                    'pos': (x_left - 2, 0.5),
                    'w': (x_right - x_left) + 4,
                    'h': 3,
                    'color': '#708090',
                    'label': f'Quay {c}'
                })
            # 列主干道
            n_in = f'C{c}_L0'
            n_out = f'C{c}_R0'
            self._add_node(n_in, (x_left, self.base_y))
            self._add_node(n_out, (x_right, self.base_y))
            self._add_edge(n_in, n_out, bidirectional=True)
            self._add_edge(n_in, q_node, bidirectional=True)
            self._add_edge(q_node, n_out, bidirectional=True)
            column_path_left = [n_in]
            column_path_right = [n_out]

            for r in range(1, num_rows + 1):
                y_pos = self.base_y + r * self.row_spacing
                node_l = f'C{c}_L{r}'
                node_r = f'C{c}_R{r}'
                self._add_node(node_l, (x_left, y_pos))
                self._add_node(node_r, (x_right, y_pos))

                if random.random() < yard_prob:
                    self.yards.append({
                        'pos': (x_left + 2, y_pos - 4),
                        'w': (x_right - x_left) - 4,
                        'h': 8,
                        'label': f'Block {c}-{r}'
                    })
                    self._add_edge(node_l, node_r, bidirectional=True)

                self._add_edge(column_path_left[-1], node_l, bidirectional=True)
                self._add_edge(column_path_right[-1], node_r, bidirectional=True)
                column_path_left.append(node_l)
                column_path_right.append(node_r)

            # 水平跨列连接
            if c > 1:
                self._add_edge(f'C{c - 1}_R0', n_in, bidirectional=True)
            else:
                self._add_edge('Gate_In', n_in, bidirectional=True)

            prev_column_nodes = [n_in, n_out]

        if prev_column_nodes:
            self._add_edge(prev_column_nodes[1], 'Gate_Out', bidirectional=True)

    def _add_node(self, name, pos):
        if name not in self.node_registry:
            self.node_registry.add(name)
            self.nodes[name] = pos

    def _add_edge(self, u, v, bidirectional=False):
        if u not in self.graph:
            self.graph[u] = []
        if v not in self.graph[u]:
            self.graph[u].append(v)
        if bidirectional:
            if v not in self.graph:
                self.graph[v] = []
            if u not in self.graph[v]:
                self.graph[v].append(u)

    def get_bounds(self):
        """返回港口布局的边界框。"""
        xs = [p[0] for p in self.nodes.values()]
        ys = [p[1] for p in self.nodes.values()]
        return {
            'x_min': min(xs) - 20,
            'x_max': max(xs) + 20,
            'y_min': min(ys) - 10,
            'y_max': max(ys) + 10
        }

