
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

from simulation import PortSimApp

if __name__ == "__main__":
    app = PortSimApp(num_trucks=4) # 启动4台车
    app.run()