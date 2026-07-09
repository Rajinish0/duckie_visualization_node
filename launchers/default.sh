#!/bin/bash

source /environment.sh

dt-launchfile-init
# rosrun my_package ros_communication.py
# rosrun localization localization.py
# rosrun visualization visualization_node.py
dt-exec rosrun visualization visualization_node.py
# dt-exec roslaunch navigation navigation.launch
dt-launchfile-join
