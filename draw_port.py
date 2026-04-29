import matplotlib.pyplot as plt
import matplotlib.patches as patches
import random
import math

class AdvancedRealisticPort:
    def __init__(self, seed=None):
        if seed: random.seed(seed)
        self.nodes = {}
        self.graph = {}
        self.yards = [] # 存储生成的堆场块
        self.zones = [] # 存储泊位区信息

    def generate(self, num_cols=8, num_rows=3, yard_prob=0.7, quay_prob=0.6):
        """
        yard_prob: 0-1 之间的概率，决定是否生成堆场块
        quay_prob: 0-1 之间的概率，决定是否生成泊位
        """
        self.nodes = {}
        self.graph = {}
        self.yards = []
        self.zones = []

        # 基础出入口
        self.nodes['Gate_In'] = (0, 10)
        self.nodes['Gate_Out'] = (num_cols * 18 + 10, 10)

        # 记录前一列的节点，用于主干道横向连接
        prev_column_nodes = []

        for c in range(1, num_cols + 1):
            x_left = c * 18 - 5
            x_right = c * 18 + 5
            
            # --- 1. 泊位 (向下延伸，靠近海) ---
            q_node = f'Q{c}'
            self.nodes[q_node] = ( (x_left+x_right)/2, 2 )
            
            if random.random() < quay_prob:
                self.zones.append({
                    'pos': (x_left - 2, 0.5), 'w': (x_right-x_left)+4, 'h': 3, 
                    'color': '#708090', 'label': f'Quay {c}'
                })
            
            # --- 2. 堆场与巷道 (向上延伸) ---
            n_in = f'C{c}_L0'; n_out = f'C{c}_R0'
            self.nodes[n_in] = (x_left, 10)
            self.nodes[n_out] = (x_right, 10)
            self._add_edge(n_in, n_out, bidirectional=True) 
            self._add_edge(n_in, q_node, bidirectional=True)  
            self._add_edge(q_node, n_out, bidirectional=True)

            column_path_left = [n_in] 
            column_path_right = [n_out]

            for r in range(1, num_rows + 1):
                y_pos = 10 + r * 12
                node_l = f'C{c}_L{r}'
                node_r = f'C{c}_R{r}'
                self.nodes[node_l] = (x_left, y_pos)
                self.nodes[node_r] = (x_right, y_pos)
                
                if random.random() < yard_prob:
                    self.yards.append({
                        'pos': (x_left + 2, y_pos - 4), 
                        'w': (x_right - x_left) - 4, 
                        'h': 8, 'label': f'Block {c}-{r}'
                    })
                    self._add_edge(node_l, node_r, bidirectional=True) 

                self._add_edge(column_path_left[-1], node_l, bidirectional=True)
                self._add_edge(column_path_right[-1], node_r, bidirectional=True)
                
                column_path_left.append(node_l)
                column_path_right.append(node_r)

            # --- 3. 横向跨列连接 ---
            if c > 1:
                self._add_edge(f'C{c-1}_R0', n_in, bidirectional=True)
            else:
                self._add_edge('Gate_In', n_in, bidirectional=True)

            prev_column_nodes = [n_in, n_out] 

        self._add_edge(prev_column_nodes[1], 'Gate_Out', bidirectional=True)

    def _add_edge(self, u, v, bidirectional=False):
        if u not in self.graph: self.graph[u] = []
        if v not in self.graph[u]: self.graph[u].append(v)
        if bidirectional:
            if v not in self.graph: self.graph[v] = []
            if u not in self.graph[v]: self.graph[v].append(u)

    def draw(self, ax=None):
        """修复版：支持外部 ax 传入"""
        if ax is None:
            fig, ax = plt.subplots(figsize=(16, 9))
        
        ax.set_facecolor('#f0f0f0') 
        
        # 绘制大海
        ax.add_patch(patches.Rectangle((-20, -5), 300, 10, color='#add8e6', zorder=0))

        # 绘制泊位区
        for quay in self.zones:
            ax.add_patch(patches.Rectangle(quay['pos'], quay['w'], quay['h'], 
                                           facecolor=quay['color'], edgecolor='black', 
                                           alpha=0.6, lw=0.5, zorder=1))
            ax.text(quay['pos'][0]+quay['w']/2, quay['pos'][1]+quay['h']/2, 
                    quay['label'], ha='center', va='center', color='white', fontsize=7, fontweight='bold')

        # 绘制堆场
        for y in self.yards:
            ax.add_patch(patches.Rectangle(y['pos'], y['w'], y['h'], 
                                           facecolor='tan', edgecolor='black', 
                                           alpha=0.8, lw=1, zorder=3))
            ax.text(y['pos'][0]+y['w']/2, y['pos'][1]+y['h']/2, 
                    y['label'], ha='center', va='center', fontsize=7, fontweight='bold')

        # 绘制路网
        for u, neighbors in self.graph.items():
            for v in neighbors:
                p1, p2 = self.nodes[u], self.nodes[v]
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='white', lw=4, zorder=1, solid_capstyle='round')
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='black', lw=0.5, alpha=0.3, zorder=2)

        # 绘制节点
        for name, pos in self.nodes.items():
            color = 'red' if 'L0' in name or 'R0' in name or 'Gate' in name else 'gray'
            size = 20 if color == 'red' else 10
            ax.scatter(pos[0], pos[1], color=color, s=size, alpha=0.6, zorder=5)

        ax.set_title("Realistic Random Port Layout with Aisles & Sea", fontsize=16)
        ax.set_aspect('equal')
        return ax