import socket
import pickle
from params import PC_PORT

class LidarReceiver:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', PC_PORT))
        self.sock.setblocking(False)
    
    def get_scan(self):
        try:
            packet, _ = self.sock.recvfrom(64000)
            return pickle.loads(packet)
        except BlockingIOError:
            return None
    
    def close(self):
        self.sock.close()
