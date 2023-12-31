import rclpy
import yaml
import numpy as np
import cv2
from .mono_video_odometry import MonoVideoOdometery
from sensor_msgs.msg import CompressedImage
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Path

image_buffer = []

def camera_callback(msg):
    global node
    global image_buffer
    np_arr = np.frombuffer(msg.data, np.uint8)
    image_np = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    image_buffer.append(image_np)

def main():
    
    # load config
    with open("/home/user/ws/src/config/config.yaml", "r") as file:
        config = yaml.safe_load(file)
    node_name = config["visual_odometry"]["node"]
    topic = config["visual_odometry"]["topic"]
    path_topic = config["visual_odometry"]["path_topic"]
    sample_rate = config["visual_odometry"]["sample_rate"]
    camera_topic = config["sensors"]["camera"]["topic"]

    # ros2 initialization
    rclpy.init(args=None)
    global node
    node = rclpy.create_node(node_name)
    vo_pub = node.create_publisher(PoseWithCovarianceStamped, topic, 10)
    path_pub = node.create_publisher(Path, path_topic, 10)
    camera_sub = node.create_subscription(CompressedImage, camera_topic, camera_callback, 10)
    rate = node.create_rate(sample_rate) # frequency in Hz
    camera_sub, vo_pub, rate
    logger = node.get_logger()
    logger.info('Visual odometry node launched.')


    # get first frame
    global image_buffer
    while len(image_buffer) == 0:
        rclpy.spin_once(node)

    first_frame = image_buffer.pop(0)
    gray = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
    vo = MonoVideoOdometery(gray)

    vo_path = Path()
    while True:
        rclpy.spin_once(node)

        if len(image_buffer) > 0:
            curr_frame = image_buffer.pop(0)
            
            gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
            T = vo.visual_odometery(gray)

            if T is not None:
                # convert homogenous coordinates to pose
                position = T[:3, 3]
                
                R = T[:3, :3]
                w = np.sqrt(1 + R[0,0] + R[1,1] + R[2,2]) / 2
                x = (R[2,1] - R[1,2]) / (4*w)
                y = (R[0,2] - R[2,0]) / (4*w)
                z = (R[1,0] - R[0,1]) / (4*w)
                
                # publish pose message
                pose_msg = PoseWithCovarianceStamped()
                pose_msg.header.stamp = node.get_clock().now().to_msg()
                pose_msg.header.frame_id = "world"
                pose_msg.pose.pose.position.x = position[0]
                pose_msg.pose.pose.position.y = position[1]
                pose_msg.pose.pose.position.z = position[2]
                pose_msg.pose.pose.orientation.x = x
                pose_msg.pose.pose.orientation.y = y
                pose_msg.pose.pose.orientation.z = z
                pose_msg.pose.pose.orientation.w = w
                pose_msg.pose.covariance = [0.1, 0, 0, 0, 0, 0,
                                            0, 0.1, 0, 0, 0, 0,
                                            0, 0, 0.1, 0, 0, 0,
                                            0, 0, 0, 0, 0.1, 0,
                                            0, 0, 0, 0, 0, 0.1]
                vo_pub.publish(pose_msg)

                # publish path message
                vo_path.header = pose_msg.header
                vo_path.poses.append(pose_msg)
                path_pub.publish(vo_path)

            else:
                logger.info("Visual odometry failed. No pose calculated.")
        

if __name__ == "__main__":
    main()