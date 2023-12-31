import numpy as np
from libs.IMU_tracker import IMUTracker
from sys import argv
import numpy as np

CALIB_DATA_SIZE = 1000

finished_callib = False
imu_data = []
mag_data = []

def position_tracker():

    imu_data = open("/home/vini/Documents/Yapira/Bedman-Trekker/src/nodes/position_tracking/data.txt")

    raw_data = []
    for line in imu_data.readlines():
        data = line.split(' ')
        raw_data.append(data[1:10]) 

    raw_data_np = np.array(raw_data, dtype=np.float32)   
    print(raw_data_np)

    tracker = IMUTracker(sampling=400)

    print("callibrating...")

    print(raw_data_np[0:CALIB_DATA_SIZE].shape)
    tracker.initialize(raw_data_np[0:CALIB_DATA_SIZE])
    print('callibration finished.')

    print('position tracking started.')
    points = []
    for data in raw_data_np[CALIB_DATA_SIZE:]:
        p = tracker.calculatePosition(data)
        print(p)
        points.append(p)

    raw_points = np.array(points)

    np.save("raw_points.npy", raw_points)

if __name__ == '__main__':
    position_tracker()
