# -*- coding: utf-8 -*-
"""e_monitor.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1wVBgDLz1lTLZfoL9lBzpU8ZUs2rPqWxF
"""

import numpy as np
import cv2
import os
import time

def load_yolo(weights_path, config_path, names_path):
    # Check if files exist
    if not os.path.exists(config_path):
        raise IOError(f"Configuration file not found: {config_path}")
    if not os.path.exists(weights_path):
        raise IOError(f"Weights file not found: {weights_path}")
    if not os.path.exists(names_path):
        raise IOError(f"Names file not found: {names_path}")

    net = cv2.dnn.readNet(weights_path, config_path)
    layer_names = net.getLayerNames()
    output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers().flatten()]
    classes = []
    with open(names_path, "r") as f:
        classes = [line.strip() for line in f.readlines()]
    return net, classes, output_layers

def zone_boundary():
    # Prompt user for number of desks
    #num_desks = int(input("Enter the number of desks: "))
    #desk_boundaries = {}
    desk_boundaries = {
    "desk1": (50, 20, 300, 480),  # (x1, y1, x2, y2)
    "desk2": (350, 20, 600, 480),
    }
    # Prompt user for boundaries of each desk
    #for i in range(1, num_desks + 1):
        #desk_name = f"desk{i}"
        #print(f"Enter boundaries for {desk_name} (x1, y1, x2, y2):")
        #x1 = int(input("x1: "))
        #y1 = int(input("y1: "))
        #x2 = int(input("x2: "))
        #y2 = int(input("y2: "))
        #desk_boundaries[desk_name] = (x1, y1, x2, y2)
    return desk_boundaries

def draw_boundary_boxes(frame, desk_boundaries):
    for desk, (x1, y1, x2, y2) in desk_boundaries.items():
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, desk, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

def intersection_area(rect1, rect2):
    x1 = max(rect1[0], rect2[0])
    y1 = max(rect1[1], rect2[1])
    x2 = min(rect1[0] + rect1[2], rect2[0] + rect2[2])
    y2 = min(rect1[1] + rect1[3], rect2[1] + rect2[3])
    if x1 < x2 and y1 < y2:
        return (x2 - x1) * (y2 - y1)
    return 0

def is_outside_boundary(box, boundary):
    person_area = box[2] * box[3]
    intersection = intersection_area(box, boundary)
    inside_ratio = intersection / person_area
    return inside_ratio < 0.3  # Less than 30% inside means more than 70% outside

def process_frame(frame, net, output_layers, classes, desk_boundaries, last_seen, alert_displayed):
    height, width, channels = frame.shape
    blob = cv2.dnn.blobFromImage(frame, 0.00392, (224, 224), (0, 0, 0), True, crop=False)
    net.setInput(blob)
    outs = net.forward(output_layers)

    class_ids = []
    confidences = []
    boxes = []

    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > 0.5 and classes[class_id] == "person":
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                x = int(center_x - w / 2)
                y = int(center_y - h / 2)
                boxes.append([x, y, w, h])
                confidences.append(float(confidence))
                class_ids.append(class_id)

    indexes = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)

    # Track if any person is in the frame for each desk
    person_in_desk = {desk: False for desk in desk_boundaries.keys()}

    for i in range(len(boxes)):
        if i in indexes:
            x, y, w, h = boxes[i]
            person_bbox = (x, y, w, h)
            for desk, boundary in desk_boundaries.items():
                if not is_outside_boundary(person_bbox, (boundary[0], boundary[1], boundary[2] - boundary[0], boundary[3] - boundary[1])):
                    person_in_desk[desk] = True
                    last_seen[desk] = time.time()  # Reset timer if person is detected inside the boundary
                    alert_displayed[desk] = False
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                else:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

    # Check alert conditions for each desk
    for desk in desk_boundaries.keys():
        if not person_in_desk[desk]:
            if time.time() - last_seen[desk] > 60:  # 60 seconds = 1 minute
                alert_displayed[desk] = True
        if alert_displayed[desk]:
            cv2.putText(frame, f"Alert: {desk} left for over 1 minute!", (50, 50 + 30 * list(desk_boundaries.keys()).index(desk)), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)

def main():
    config_path = input("Enter the path for the YOLO configuration file: ")
    weights_path = input("Enter the path for the YOLO weights file: ")
    names_path = input("Enter the path for the COCO names file: ")

    net, classes, output_layers = load_yolo(weights_path, config_path, names_path)

    desk_boundaries = zone_boundary()

    last_seen = {desk: time.time() for desk in desk_boundaries.keys()}
    alert_displayed = {desk: False for desk in desk_boundaries.keys()}

    cap = cv2.VideoCapture(0)  # Change 0 to your camera source

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        draw_boundary_boxes(frame, desk_boundaries)
        process_frame(frame, net, output_layers, classes, desk_boundaries, last_seen, alert_displayed)
        cv2.imshow("Frame", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()