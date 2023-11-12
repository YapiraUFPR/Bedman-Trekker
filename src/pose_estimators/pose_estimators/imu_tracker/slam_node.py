from libs.IMU_tracker import IMUTracker
import rclpy
import yaml
from geometry_msgs.msg import PoseStamped
from custom_messages.msg import Imu9DOF
import numpy as np

CALIB_DATA_SIZE = 1000

imu_data = []

def imu_callback(msg:Imu9DOF):
    global imu_data
    imu_data = [msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z, 
                msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z,
                msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w]

def main():
    # load config
    with open("/home/user/ws/src/config/config.yaml", "r") as file:
        config = yaml.safe_load(file)
    node_name = config["tracker"]["node"]
    pos_topic = config["tracker"]["topic"]
    sample_rate = config["tracker"]["sample_rate"]
    topic = config["imu"]["topic"]
    imu_sample_rate = config["imu"]["sample_rate"]

    # ros2 initialization
    rclpy.init()
    global node
    node = rclpy.create_node(node_name)
    imu_sub = node.create_subscription(Imu9DOF, topic, imu_callback, 10)
    pos_pub = node.create_publisher(PoseStamped, pos_topic, 10)
    rate = node.create_rate(sample_rate)  # frequency in Hz
    imu_sub, pos_pub, rate  # prevent unused variable warning
    logger = node.get_logger()
    logger.info('Tracker node launched.')

    tracker = IMUTracker(imu_sample_rate)
    
    global imu_data
    
    # calibrate tracker when IMU is stationary
    node.get_logger().info('Waiting for callibration data. Keep the IMU stationary...')
    callib_data = []
    while not finished_callib:
        rclpy.spin_once(node)
        if imu_data:
            callib_data.append(imu_data)
            imu_data = []

        if len(callib_data) > CALIB_DATA_SIZE:
            finished_callib = True

    callib_data_np = np.array(callib_data, dtype=np.float32)
    tracker.initialize(callib_data_np)
    logger.info('Callibration finished.')

    logger.info('Position tracking started.')
    while True:
        rclpy.spin_once(node)

        np_data =  np.array(imu_data, dtype=np.float32)

        p = tracker.calculatePosition(np_data)

        # publish position
        msg = PoseStamped()
        msg.header.stamp = node.get_clock().now().to_msg()
        msg.pose.position.x = p[0]
        msg.pose.position.y = p[1]
        msg.pose.position.z = p[2]


        pos_pub.publish(msg)

if __name__ == '__main__':
    main()