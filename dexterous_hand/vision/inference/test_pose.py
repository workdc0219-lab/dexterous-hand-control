#!/usr/bin/env python3
"""
Test YOLOv8-pose inference.

Usage:
    # Test with image
    python test_pose.py --source image.jpg

    # Test with video
    python test_pose.py --source video.mp4

    # Test with camera (if available)
    python test_pose.py --source 0
"""

import argparse
import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO


def parse_args():
    parser = argparse.ArgumentParser(description="Test YOLOv8-pose inference")
    parser.add_argument("--source", type=str, default="0",
                        help="Image/video path or camera index (default: 0)")
    parser.add_argument("--model", type=str, default="yolov8n-pose.pt",
                        help="Model path (default: yolov8n-pose.pt)")
    parser.add_argument("--conf", type=float, default=0.5,
                        help="Confidence threshold (default: 0.5)")
    parser.add_argument("--show", action="store_true",
                        help="Show visualization")
    parser.add_argument("--save", type=str, default=None,
                        help="Save output path")
    return parser.parse_args()


def draw_keypoints(image, results, conf_threshold=0.5):
    """Draw keypoints and skeleton on image."""
    # COCO keypoint connections
    skeleton = [
        (0, 1), (0, 2), (1, 3), (2, 4),  # Head
        (5, 7), (7, 9), (6, 8), (8, 10),  # Arms
        (5, 6), (5, 11), (6, 12),  # Torso
        (11, 13), (13, 15), (12, 14), (14, 16)  # Legs
    ]
    colors = [
        (255, 0, 0), (0, 255, 0), (255, 0, 0), (0, 255, 0),
        (255, 0, 0), (0, 0, 255), (255, 0, 0), (0, 0, 255),
        (255, 255, 0), (255, 0, 0), (255, 0, 0),
        (0, 0, 255), (0, 255, 0), (0, 0, 255), (0, 255, 0)
    ]

    for result in results:
        if result.keypoints is None:
            continue

        kpts = result.keypoints.xy[0].cpu().numpy()  # (17, 2)
        confs = result.keypoints.conf[0].cpu().numpy()  # (17,)

        # Draw skeleton
        for i, (start, end) in enumerate(skeleton):
            if confs[start] > conf_threshold and confs[end] > conf_threshold:
                pt1 = (int(kpts[start][0]), int(kpts[start][1]))
                pt2 = (int(kpts[end][0]), int(kpts[end][1]))
                cv2.line(image, pt1, pt2, colors[i], 2)

        # Draw keypoints
        for i, (kpt, conf) in enumerate(zip(kpts, confs)):
            if conf > conf_threshold:
                x, y = int(kpt[0]), int(kpt[1])
                cv2.circle(image, (x, y), 4, (0, 255, 0), -1)
                cv2.putText(image, f"{conf:.2f}", (x + 5, y - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)

    return image


def main():
    args = parse_args()

    # Load model
    print(f"Loading model: {args.model}")
    model = YOLO(args.model)
    print("Model loaded successfully!")

    # Parse source
    source = args.source
    if source.isdigit():
        source = int(source)

    # Process
    if isinstance(source, int) or Path(source).suffix in ['.mp4', '.avi', '.mov']:
        # Video or camera
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            print(f"Error: Cannot open source {source}")
            return

        fps_list = []
        frame_count = 0

        print("Processing video... Press 'q' to quit")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Inference
            import time
            start = time.time()
            results = model(frame, conf=args.conf, verbose=False)
            elapsed = time.time() - start
            fps_list.append(1.0 / elapsed if elapsed > 0 else 0)

            # Draw
            annotated = draw_keypoints(frame.copy(), results, args.conf)

            # Add FPS
            fps = fps_list[-1]
            cv2.putText(annotated, f"FPS: {fps:.1f}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            frame_count += 1

            if args.show:
                cv2.imshow("YOLOv8-pose", annotated)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            if args.save:
                if frame_count == 1:
                    h, w = annotated.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    writer = cv2.VideoWriter(args.save, fourcc, 30, (w, h))
                writer.write(annotated)

        cap.release()
        if args.save and frame_count > 0:
            writer.release()
            print(f"Saved to {args.save}")

        if fps_list:
            print(f"\nStatistics:")
            print(f"  Frames: {frame_count}")
            print(f"  Avg FPS: {np.mean(fps_list):.1f}")
            print(f"  Min FPS: {np.min(fps_list):.1f}")
            print(f"  Max FPS: {np.max(fps_list):.1f}")

    else:
        # Single image
        image = cv2.imread(source)
        if image is None:
            print(f"Error: Cannot read image {source}")
            return

        results = model(image, conf=args.conf, verbose=False)
        annotated = draw_keypoints(image.copy(), results, args.conf)

        if args.show:
            cv2.imshow("YOLOv8-pose", annotated)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        if args.save:
            cv2.imwrite(args.save, annotated)
            print(f"Saved to {args.save}")

        # Print results
        for i, result in enumerate(results):
            if result.keypoints is not None:
                print(f"\nDetection {i}:")
                print(f"  Keypoints: {result.keypoints.xy.shape[1]}")
                print(f"  Confidence: {result.boxes.conf.mean():.3f}")

    print("\nDone!")


if __name__ == "__main__":
    main()
