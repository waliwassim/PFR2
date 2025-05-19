import matplotlib.pyplot as plt
from params import *

class ICPVisualizer:
    def __init__(self):
        plt.ion()
        self.fig, (self.ax_scan, self.ax_map) = plt.subplots(1, 2, figsize=(12, 6))
        
        # Scan actuel
        self.ax_scan.set_title("Scan LiDAR actuel")
        self.scan_plot, = self.ax_scan.plot([], [], 'r.', markersize=2)
        
        # Carte de référence
        self.ax_map.set_title("Carte ICP")
        self.map_plot, = self.ax_map.plot([], [], 'b.', markersize=1)
        
        self._setup_axes()
    
    def _setup_axes(self):
        for ax in [self.ax_scan, self.ax_map]:
            ax.set_xlim(-5, 5)
            ax.set_ylim(-5, 5)
            ax.grid(True)
            ax.set_aspect('equal')
    
    def update(self, scan_points, map_points):
        self.scan_plot.set_data(scan_points[:,0], scan_points[:,1])
        self.map_plot.set_data(map_points[:,0], map_points[:,1])
        self.fig.canvas.draw_idle()
        plt.pause(0.01)
