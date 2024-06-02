#!/bin/bash
cd /home/$USER/bedman-trekker

# Optionally run foxglove bridge
bash run_foxglove_bridge.sh &

docker run --rm --name interII --privileged -it --ipc="host" --gpus all --network="host" -v $PWD:/home/user/ws/ -v /tmp.X11-unix:/tmp/.X11-unix -v /dev:/dev -v /tmp/argus_socket:/tmp/argus_socket --cap-add SYS_PTRACE -e DISPLAY=$DISPLAY -w /home/user/ws/ --volume="$HOME/.Xauthority:/root/.Xauthority:rw" yapira/bedman:latest 'source /home/user/ws/install/setup.bash; ros2 launch interii.launch.py'