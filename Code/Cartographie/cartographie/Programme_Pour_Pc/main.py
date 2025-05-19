from lidar_network import LidarReceiver
from icp_processor import ICPLocalizer
from visualization import ICPVisualizer
import time
from params import PLOT_REFRESH_RATE

def main():
    lidar = LidarReceiver()
    icp = ICPLocalizer()
    viz = ICPVisualizer()
    last_update = time.time()

    try:
        while True:
            scan = lidar.get_scan()
            if scan:
                result = icp.process_scan(scan)
                if result and (time.time() - last_update > PLOT_REFRESH_RATE):
                    viz.update(
                        np.asarray(result.points)[:,:2],
                        np.asarray(icp.reference_map.points)[:,:2]
                    )
                    last_update = time.time()
            time.sleep(0.005)
    except KeyboardInterrupt:
        print("\nArrêt propre")
    finally:
        lidar.close()

if __name__ == "__main__":
    main()
