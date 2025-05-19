import numpy as np
import open3d as o3d
from params import *

def raw_scan_to_points(scan_data, angle_bins=360):
    """Convertit le format brut du LiDAR en tableau numpy"""
    arr = np.full(angle_bins, np.nan)
    for _, angle, dist in scan_data:
        if dist <= 0: continue
        deg = int(angle) % angle_bins
        arr[deg] = dist / 1000.0  # Conversion mm -> m
    return arr

def clean_pointcloud(pcd):
    """Filtrage du nuage de points"""
    pcd = pcd.voxel_down_sample(VOXEL_SIZE)
    return pcd.remove_statistical_outlier(OUTLIER_NB, OUTLIER_STD)[0]
