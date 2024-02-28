#!/usr/bin/env python3
import rclpy
import yaml
from sensor_msgs.msg import BatteryState
from sys import argv
from time import sleep
from .libs.adafruit_ina219 import INA219
from .libs.adafruit_bitbangio import I2C
import board

def main():

    # load config
    with open("/home/user/ws/src/config/config.yaml", "r") as file:
        config = yaml.safe_load(file)
    node_name = config["sensors"]["battery"]["node"]
    topic = config["sensors"]["battery"]["topic"]
    sample_rate = config["sensors"]["battery"]["sample_rate"]
    max_cell_voltage = config["sensors"]["battery"]["max_cell_voltage"]
    min_cell_voltage = config["sensors"]["battery"]["min_cell_voltage"]
    cells = config["sensors"]["battery"]["cells"]
    capacity = config["sensors"]["battery"]["capacity"]

    max_voltage = max_cell_voltage * cells
    min_voltage = min_cell_voltage * cells

    # ros2 initialization
    rclpy.init(args=argv)
    global node
    node = rclpy.create_node(node_name)
    pub = node.create_publisher(BatteryState, topic, 10)
    rate = node.create_rate(sample_rate)  # frequency in Hz
    logger = node.get_logger()
    logger.info('Battery sensor node launched.')

    # sensor initialization
    ina219 = None
    timeout = 5
    while ina219 is None:
        logger.info('Initializing sensor INA219...')

        try:
            i2c = I2C(scl=board.D5, sda=board.D6, frequency=sample_rate*1000)
            ina219 = INA219(i2c)
            ina219.set_calibration_16V_5A()
        except Exception as e:
            ina219 = None
            logger.error(f"Failed to initialize INA219: {e}")
            logger.error(f"Retrying in {timeout} seconds...")
            sleep(timeout)
            timeout *= 2

    # main loop
    logger.info('Publishing battery data...')
    while rclpy.ok():
        msg = BatteryState()
        msg.header.stamp = node.get_clock().now().to_msg()

        bus_voltage = ina219.bus_voltage
        # shunt_voltage = ina219.shunt_voltage
        current = ina219.current
        # power = ina219.power
        percentage = (bus_voltage - min_voltage) / (max_voltage - min_voltage)

        msg.voltage = bus_voltage
        msg.current = current
        msg.charge = percentage * capacity
        msg.capacity = capacity
        msg.design_capacity = capacity
        msg.percentage = percentage

        msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        msg.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_LIPO
        msg.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_GOOD

        msg.present = True

        pub.publish(msg)

        sleep(1/sample_rate)

if __name__ == "__main__":
    main()