#!/usr/bin/env python3
import math
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from map_graph import RoadGraph, load_graph_from_yaml, Direction

import config

# Placeholder start position for local debugging, before a live pose feed
# is wired in. Swap this out (or drive it from set_robot_pose) once the
# real navigation_node/EKF is running.
# DEBUG_START_X = 0.88
# DEBUG_START_X = 1.8625
# DEBUG_START_X = 2.6325
# DEBUG_START_Y = 3.2175
DEBUG_START_X = 1.4625
DEBUG_START_Y = 0.2925
# DEBUG_START_Y = 0.2925
# DEBUG_START_Y = 0.3425
# DEBUG_THETA = -math.pi/2
DEBUG_THETA = 0.0
# DEBUG_START_Y = 3.14


class VisualApp:
    """Pure Tkinter view. Knows nothing about ROS - the wrapper node feeds
    it data through the methods below and reads clicks back out through
    register_goal_callback. Also does its own local path planning on 'Go!'
    for instant feedback / offline debugging - independent of whether a
    real navigation_node is running anywhere."""

    LANDMARK_IDLE_COLOR = "yellow"
    LANDMARK_DETECTED_COLOR = "green"

    def __init__(self, root):
        self.root = root
        self.root.title("Duckietown Mission Control")

        self.instruction_label = tk.Label(
            root, text="Click on the map to set a destination, then press 'Go!'",
            font=("Arial", 12))
        self.instruction_label.pack(pady=5)

        self.coord_label = tk.Label(root, text="Target: None", font=("Arial", 10), fg="blue")
        self.coord_label.pack()

        self.plan_label = tk.Label(root, text="Path: -  |  Turns: -",
                                    font=("Arial", 10), fg="darkorange")
        self.plan_label.pack()

        self.canvas = tk.Canvas(root, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        try:
            self.map_image = Image.open("packages/navigation/src/images/map_image.png")
            self.map_photo = ImageTk.PhotoImage(self.map_image)
            self.canvas.config(width=self.map_image.width, height=self.map_image.height)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.map_photo)
            self.scale_x = config.TILE_SIZE_X / (self.map_image.width / config.NUM_TILES_X)
            self.scale_y = config.TILE_SIZE_Y / (self.map_image.height / config.NUM_TILES_Y)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load map image:\n{e}")

        self.target_pixel = None
        self.target_world = None
        self.marker = None

        self.canvas.bind("<Button-1>", self.on_map_click)

        self.go_button = tk.Button(root, text="Go!", font=("Arial", 14, "bold"),
                                    bg="green", fg="white", command=self.send_goal)
        self.go_button.pack(pady=10)

        self.new_goal_callback = None

        self.graph = load_graph_from_yaml("packages/navigation/src/virtual.yaml")
        # self.graph.add_node_with_splice("START", DEBUG_START_X, DEBUG_START_Y)
        self.visualize_road_graph(self.graph)

        # live-robot drawing state
        self.robot_marker = None
        self.robot_heading = None
        self.cov_ellipse = None
        self.landmarks_drawn = False
        self.landmark_rects = {}   # tag_id -> canvas rectangle item id

    # ---------------- static graph ----------------
    def on_map_click(self, event):
        x, y = event.x, event.y
        self.target_pixel = (x, y)
        self.target_world = self.pixel_to_world(x, y)

        self.coord_label.config(
            text=f"Target Pixel: ({x}, {y}) | Target World: "
                 f"({self.target_world[0]:.2f}m, {self.target_world[1]:.2f}m)")

        if self.marker:
            self.canvas.delete(self.marker)
        r = 5
        self.marker = self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                               fill="red", outline="black")

    def register_goal_callback(self, callback):
        self.new_goal_callback = callback

    def pixel_to_world(self, px, py):
        world_x = (px * self.scale_x) + config.OFFSET_X
        py_flipped = self.map_image.height - py
        world_y = (py_flipped * self.scale_y) + config.OFFSET_Y
        return (world_x, world_y)

    def world_to_pixel(self, world_x, world_y):
        px = (world_x - config.OFFSET_X) / self.scale_x
        py_flipped = (world_y - config.OFFSET_Y) / self.scale_y
        py = self.map_image.height - py_flipped
        return (px, py)

    def visualize_road_graph(self, graph: RoadGraph):
        for _, node in graph.nodes.items():
            start_px, start_py = self.world_to_pixel(node.x, node.y)
            for edge in node.edges:
                target_node = graph.nodes[edge.to_node]
                end_px, end_py = self.world_to_pixel(target_node.x, target_node.y)
                self.canvas.create_line(
                    start_px, start_py, end_px, end_py,
                    fill='green', width=2, arrow=tk.LAST, arrowshape=(10, 12, 4))

        for _, node in graph.nodes.items():
            px, py = self.world_to_pixel(node.x, node.y)
            node_color = 'red' if node.is_phantom else 'blue'
            self.canvas.create_oval(px - 6, py - 6, px + 6, py + 6,
                                     fill=node_color, outline='black', width=2)
            self.canvas.create_text(px + 10, py - 10, text=node.name,
                                     fill="black", font=("Arial", 10, "bold"))

    # ---------------- goal + local debug planning ----------------
    def send_goal(self):
        if not self.target_world:
            messagebox.showwarning("Hold up", "Please click a destination on the map first.")
            return

        # self._plan_locally(self.target_world)

        if self.new_goal_callback is not None:
            self.new_goal_callback(self.target_world)

    def _plan_locally(self, goal_world):
        """Compute and draw a path/turn-list right here, with no ROS
        involved. If a real navigation_node is also running, its authoritative
        plan will arrive moments later over /navigation/path and simply
        overwrite this one."""
        # self.graph.restore_graph(["GOAL"])  # kee START fixed, drop any earlier GOAL splice
        self.graph.restore_graph(["START", "GOAL"])
        heading = Direction.from_angle(DEBUG_THETA)
        start, forbidden = self.graph.add_start_node_with_splice("START", DEBUG_START_X, DEBUG_START_Y, heading)
        goal = self.graph.add_node_with_splice("GOAL", *goal_world)

        try:
            nodes_seq, edges_seq = self.graph.shortest_path(start, goal, forbidden)
        except (KeyError, ValueError) as e:
            messagebox.showerror("Planning failed", str(e))
            return

        print(Direction.from_angle(0))
        turns = self.graph.path_to_turns_and_target_coords(edges_seq, nodes_seq, heading)
        path_world = [[self.graph.nodes[n].x, self.graph.nodes[n].y] for n in nodes_seq]

        self.draw_path(path_world)
        self.plan_label.config(
            text=f"Path: {' -> '.join(nodes_seq)}  |  "
                 f"Turns: {', '.join(map(str, turns)) if turns else '(none - already there)'}")

    # ---------------- z-order ----------------
    def _reassert_z_order(self):
        """Bottom -> top: map, road graph, landmarks, path, robot. Safe to
        call even if some tags have no items yet - raising an empty tag is
        a no-op, not an error."""
        self.canvas.tag_raise("landmark")
        self.canvas.tag_raise("path_line")
        self.canvas.tag_raise("robot")

    # ---------------- path ----------------
    def draw_path(self, path_world: list):
        """path_world: list of [x, y] world coordinates, in travel order."""
        self.canvas.delete("path_line")
        if not path_world or len(path_world) < 2:
            return
        for (x1, y1), (x2, y2) in zip(path_world, path_world[1:]):
            px1, py1 = self.world_to_pixel(x1, y1)
            px2, py2 = self.world_to_pixel(x2, y2)
            self.canvas.create_line(px1, py1, px2, py2, fill="orange", width=5,
                                     tags="path_line", capstyle=tk.ROUND)
        self._reassert_z_order()

    # ---------------- landmarks (AprilTags) ----------------
    def draw_landmarks(self, landmarks: list):
        if self.landmarks_drawn:
            return
        for lm in landmarks:
            px, py = self.world_to_pixel(lm["x"], lm["y"])
            s = 6
            rect = self.canvas.create_rectangle(
                px - s, py - s, px + s, py + s,
                fill=self.LANDMARK_IDLE_COLOR, outline="black", width=2, tags="landmark")
            self.canvas.create_text(
                px, py - 14, text=str(lm["id"]), fill="black",
                font=("Arial", 9, "bold"), tags="landmark")
            self.landmark_rects[lm["id"]] = rect
        self.landmarks_drawn = True
        self._reassert_z_order()

    def set_detected_landmarks(self, detected_ids: list):
        detected = set(detected_ids)
        for tag_id, rect in self.landmark_rects.items():
            color = self.LANDMARK_DETECTED_COLOR if tag_id in detected else self.LANDMARK_IDLE_COLOR
            self.canvas.itemconfig(rect, fill=color)

    # ---------------- live robot pose + uncertainty ----------------
    def set_robot_pose(self, x: float, y: float, theta: float, cov_xy=None):
        if cov_xy is not None:
            self._draw_cov_ellipse(x, y, cov_xy)

        px, py = self.world_to_pixel(x, y)
        heading_len = 18
        hx = px + heading_len * math.cos(theta)
        hy = py - heading_len * math.sin(theta)

        r = 7
        if self.robot_marker is None:
            self.robot_marker = self.canvas.create_oval(
                px - r, py - r, px + r, py + r,
                fill="cyan", outline="black", width=2, tags="robot")
            self.robot_heading = self.canvas.create_line(
                px, py, hx, hy, fill="black", width=2, arrow=tk.LAST, tags="robot")
        else:
            self.canvas.coords(self.robot_marker, px - r, py - r, px + r, py + r)
            self.canvas.coords(self.robot_heading, px, py, hx, hy)
        self._reassert_z_order()

    def _draw_cov_ellipse(self, world_x, world_y, cov_xy, n_std: float = 2.0):
        var_x, cov, var_y = cov_xy
        tr = var_x + var_y
        det = var_x * var_y - cov * cov
        disc = max(tr * tr / 4 - det, 0.0)
        root_disc = math.sqrt(disc)
        eig1 = tr / 2 + root_disc
        eig2 = max(tr / 2 - root_disc, 0.0)
        angle = math.atan2(eig1 - var_x, cov)

        a = n_std * math.sqrt(eig1)
        b = n_std * math.sqrt(eig2)

        points = []
        for i in range(24):
            t = 2 * math.pi * i / 24
            ex, ey = a * math.cos(t), b * math.sin(t)
            wx = world_x + ex * math.cos(angle) - ey * math.sin(angle)
            wy = world_y + ex * math.sin(angle) + ey * math.cos(angle)
            px, py = self.world_to_pixel(wx, wy)
            points.extend([px, py])

        if self.cov_ellipse is None:
            self.cov_ellipse = self.canvas.create_polygon(
                *points, outline="magenta", fill="", width=2, tags="robot")
        else:
            self.canvas.coords(self.cov_ellipse, *points)

    # ---------------- status ----------------
    def set_status(self, text: str):
        self.instruction_label.config(text=text)


if __name__ == "__main__":
    root = tk.Tk()
    app = VisualApp(root)
    root.mainloop()