#!/usr/bin/env python3
import os
import math
import json
import rospy
import tkinter as tk
from std_msgs.msg import String, Bool
from nav_msgs.msg import Odometry

from visual_app import VisualApp


class VisualizationNode:
    def __init__(self, root):
        self.veh = os.environ["VEHICLE_NAME"]
        self.app = VisualApp(root)
        self.app.register_goal_callback(self.on_goal)

        self.goal_pub = rospy.Publisher(f"/{self.veh}/navigation/goal", String, queue_size=1)

        # rospy callbacks run on background threads; Tkinter is not
        # thread-safe, so nothing here touches the canvas directly - it just
        # stashes data for _poll (running on the Tk main thread) to pick up.
        self._pending_pose = None
        self._pending_landmarks = None
        self._pending_path = None
        self._pending_status = None
        self._pending_detected = None
        root.after(50, self._poll)

        rospy.Subscriber(f"/{self.veh}/ekf_localization_node/pose", Odometry, self.on_pose)
        rospy.Subscriber(f"/{self.veh}/navigation/landmarks", String, self.on_landmarks)
        rospy.Subscriber(f"/{self.veh}/navigation/path", String, self.on_path)
        rospy.Subscriber(f"/{self.veh}/navigation/status", String, self.on_status)
        rospy.Subscriber(f"/{self.veh}/navigation/arrived", Bool, self.on_arrived)
        rospy.Subscriber(f"/{self.veh}/navigation/detected_landmarks", String, self.on_detected)

    def on_goal(self, world_xy):
        x, y = world_xy
        self.goal_pub.publish(String(data=f"{x},{y}"))

    def on_pose(self, msg):
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        qz, qw = msg.pose.pose.orientation.z, msg.pose.pose.orientation.w
        theta = 2.0 * math.atan2(qz, qw)
        c = msg.pose.covariance
        self._pending_pose = (x, y, theta, (c[0], c[1], c[7]))

    def on_landmarks(self, msg):
        print("recieved land marks", msg)
        self._pending_landmarks = json.loads(msg.data)

    def on_path(self, msg):
        print('received path', msg)
        self._pending_path = json.loads(msg.data)

    def on_status(self, msg):
        self._pending_status = msg.data

    def on_arrived(self, msg):
        if msg.data:
            self._pending_status = "ARRIVED"
    
    def on_detected(self, msg):
        self._pending_detected = json.loads(msg.data)

    def _poll(self):
        if self._pending_pose is not None:
            self.app.set_robot_pose(*self._pending_pose)
            self._pending_pose = None
        if self._pending_landmarks is not None:
            self.app.draw_landmarks(self._pending_landmarks)
            self._pending_landmarks = None
        if self._pending_path is not None:
            self.app.draw_path(self._pending_path)
            self._pending_path = None
        if self._pending_status is not None:
            self.app.set_status(self._pending_status)
            self._pending_status = None
        if self._pending_detected is not None:
            self.app.set_detected_landmarks(self._pending_detected)
            self._pending_detected = None
        self.app.root.after(50, self._poll)


if __name__ == "__main__":
    root = tk.Tk()
    rospy.init_node("visualization_node", anonymous=False, disable_signals=True)
    VisualizationNode(root)
    while not rospy.is_shutdown():
        root.update_idletasks()
        root.update()