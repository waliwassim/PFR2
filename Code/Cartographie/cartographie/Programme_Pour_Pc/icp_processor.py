import numpy as np
import open3d as o3d
from params import *
from pointcloud_tools import *

class ICPLocalizer:
    def __init__(self):
        self.reference_map = o3d.geometry.PointCloud()
        self.current_pose = np.eye(4)
    
    def process_scan(self, raw_scan):
        # Conversion et nettoyage
        arr = raw_scan_to_points(raw_scan)
        if np.all(np.isnan(arr)): return None
        
        scan_pcd = o3d.geometry.PointCloud()
        scan_pcd.points = o3d.utility.Vector3dVector(
            np.vstack([arr[~np.isnan(arr)] * np.cos(np.deg2rad(np.arange(360)[~np.isnan(arr)])),
                            arr[~np.isnan(arr)] * np.sin(np.deg2rad(np.arange(360)[~np.isnan(arr)]))
                        ]).T)
        
        scan_pcd = clean_pointcloud(scan_pcd)
        if len(scan_pcd.points) < 10: return None

        # Alignement ICP
        if not self.reference_map.has_points():
            self.reference_map = scan_pcd
            return scan_pcd
        
        reg_result = o3d.pipelines.registration.registration_icp(
            scan_pcd, self.reference_map, ICP_MAX_DISTANCE,
            self.current_pose,
            o3d.pipelines.registration.TransformationEstimationPointToPoint(),
            o3d.pipelines.registration.ICPConvergenceCriteria(
                max_iteration=ICP_MAX_ITERATIONS))
        
        if reg_result.fitness >= ICP_FITNESS_THRESH:
            self.current_pose = reg_result.transformation
            scan_pcd.transform(self.current_pose)
            self.reference_map += scan_pcd
            self.reference_map = self.reference_map.voxel_down_sample(VOXEL_SIZE)
        
        return scan_pcd
