import socket
import pickle
from rplidar import RPLidar

# Config LiDAR
PORT_NAME = '/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0'
BAUDRATE = 115200
TIMEOUT = 2

# Config UDP
PC_IP = '192.168.1.100'     # mettre l'IP du PC
PC_PORT = 9000
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

lidar = RPLidar(PORT_NAME, baudrate=BAUDRATE, timeout=TIMEOUT)
lidar.start_motor()

try:
    for scan in lidar.iter_scans(max_buf_meas=500):
        # Sérialisation et envoi
        data = pickle.dumps(scan)
        sock.sendto(data, (PC_IP, PC_PORT))
finally:
    lidar.stop()
    lidar.stop_motor()
    lidar.disconnect()
    sock.close()
