import matplotlib.pyplot as plt
import matplotlib.patches as patches
import random
import math


class AdvancedRealisticPort:
    """现实风格港口布局生成器。

    支持可配置的网格规模，分离数据生成与渲染逻辑，
    适用于从 8x3 到 20x10 的大规模港口场景。
    """

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
        """生成港口布局。

        Args:
            num_cols: 列数 (8~20)
            num_rows: 行数 (3~10)
            yard_prob: 堆场块生成概率
            quay_prob: 泊位生成概率
        """
        self.nodes = {}
        self.graph = {}
        self.yards = []
        self.zones = []
        self.node_registry = set()

        # 动态间距（大规模时压缩间距）
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

            # 泊位
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

    def draw(self, ax=None):
        """Matplotlib 渲染（用于调试和本地显示）。"""
        if ax is None:
            fig, ax = plt.subplots(figsize=(16, 9))

        ax.set_facecolor('#f0f0f0')
        bounds = self.get_bounds()

        # 海
        ax.add_patch(patches.Rectangle(
            (bounds['x_min'], -5), bounds['x_max'] - bounds['x_min'], 15,
            color='#add8e6', zorder=0
        ))

        # 泊位区
        for quay in self.zones:
            ax.add_patch(patches.Rectangle(
                quay['pos'], quay['w'], quay['h'],
                facecolor=quay['color'], edgecolor='black',
                alpha=0.6, lw=0.5, zorder=1
            ))
            ax.text(
                quay['pos'][0] + quay['w'] / 2, quay['pos'][1] + quay['h'] / 2,
                quay['label'], ha='center', va='center',
                color='white', fontsize=7, fontweight='bold'
            )

        # 堆场
        for y in self.yards:
            ax.add_patch(patches.Rectangle(
                y['pos'], y['w'], y['h'],
                facecolor='tan', edgecolor='black',
                alpha=0.8, lw=1, zorder=3
            ))
            ax.text(
                y['pos'][0] + y['w'] / 2, y['pos'][1] + y['h'] / 2,
                y['label'], ha='center', va='center',
                fontsize=7, fontweight='bold'
            )

        # 路网
        for u, neighbors in self.graph.items():
            for v in neighbors:
                p1, p2 = self.nodes[u], self.nodes[v]
                ax.plot(
                    [p1[0], p2[0]], [p1[1], p2[1]],
                    color='white', lw=4, zorder=1, solid_capstyle='round'
                )
                ax.plot(
                    [p1[0], p2[0]], [p1[1], p2[1]],
                    color='black', lw=0.5, alpha=0.3, zorder=2
                )

        # 节点
        for name, pos in self.nodes.items():
            color = 'red' if ('L0' in name or 'R0' in name or 'Gate' in name) else 'gray'
            size = 20 if color == 'red' else 10
            ax.scatter(pos[0], pos[1], color=color, s=size, alpha=0.6, zorder=5)

        ax.set_title("Port Layout", fontsize=14)
        ax.set_aspect('equal')
        ax.set_xlim(bounds['x_min'], bounds['x_max'])
        ax.set_ylim(bounds['y_min'], bounds['y_max'])
        return ax
