from fastapi import FastAPI, File, UploadFile
import cv2
import numpy as np
from ultralytics import YOLO
from paddleocr import PaddleOCR
import math

app = FastAPI()

# モデル読み込み（Renderでは /models に置く想定）
yolo_model = YOLO("models/openings_model.pt")
ocr_model = PaddleOCR(lang="japan", use_angle_cls=True)


def extract_wall_lines(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    thresh = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11, 2
    )

    edges = cv2.Canny(thresh, 50, 150)

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi/180,
        threshold=80,
        minLineLength=40,
        maxLineGap=5
    )

    wall_lines = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            wall_lines.append([x1, y1, x2, y2])

    return wall_lines


def calc_wall_length_mm(wall_lines, scale_mm_per_pixel):
    total = 0
    for x1, y1, x2, y2 in wall_lines:
        px = math.dist((x1, y1), (x2, y2))
        total += px * scale_mm_per_pixel
    return total


def link_openings_with_dimensions(openings, dimensions, max_distance_px=250):
    linked = []

    for op in openings:
        ox = (op["x1"] + op["x2"]) / 2
        oy = (op["y1"] + op["y2"]) / 2

        best_width = None
        best_height = None
        best_width_dist = 999999
        best_height_dist = 999999

        for dim in dimensions:
            tx, ty = dim["x"], dim["y"]
            dist = math.dist((ox, oy), (tx, ty))

            if dist > max_distance_px:
                continue

            horizontal_diff = abs(ty - oy)
            vertical_diff = abs(tx - ox)

            if horizontal_diff < vertical_diff:
                if dist < best_width_dist:
                    best_width_dist = dist
                    best_width = dim
            else:
                if dist < best_height_dist:
                    best_height_dist = dist
                    best_height = dim

        width_mm = best_width["value_mm"] if best_width else None
        height_mm = best_height["value_mm"] if best_height else None

        if op["label"] == "balcony_window":
            if height_mm is None:
                height_mm = 2000

        if op["label"] == "door":
            if height_mm is None:
                height_mm = 2000

        linked.append({
            "opening": op,
            "width_mm": width_mm,
            "height_mm": height_mm
        })

    return linked


def calculate_wallpaper_area(linked_openings, wall_length_mm, ceiling_height_mm):
    wall_area_mm2 = wall_length_mm * ceiling_height_mm
    opening_area_mm2 = 0

    for item in linked_openings:
        w = item["width_mm"]
        h = item["height_mm"]
        if w and h:
            opening_area_mm2 += w * h

    wallpaper_area_mm2 = wall_area_mm2 - opening_area_mm2

    return {
        "wall_area_m2": wall_area_mm2 / 1_000_000,
        "opening_area_m2": opening_area_mm2 / 1_000_000,
        "wallpaper_area_m2": wallpaper_area_mm2 / 1_000_000
    }


@app.post("/analyze_floorplan")
async def analyze_floorplan(
    file: UploadFile = File(...),
    ceiling_height_mm: float = 2400,
    scale_mm_per_pixel: float = 1.2
):
    contents = await file.read()
    img_np = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

    wall_lines = extract_wall_lines(img)
    wall_length_mm = calc_wall_length_mm(wall_lines, scale_mm_per_pixel)

    yolo_results = yolo_model(img)
    openings = []
    for r in yolo_results:
        for box in r.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cls = int(box.cls[0])
            label = yolo_model.names[cls]
            openings.append({
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "label": label
            })

    ocr_results = ocr_model.ocr(img, cls=True)
    dimensions = []
    for line in ocr_results:
        for box, (text, confidence) in line:
            raw = text.strip()
            if raw.replace(".", "").isdigit():
                value = float(raw)
                x = box[0][0]
                y = box[0][1]
                dimensions.append({
                    "text": raw,
                    "value_mm": value * scale_mm_per_pixel,
                    "x": x,
                    "y": y
                })

    linked = link_openings_with_dimensions(openings, dimensions)
    result = calculate_wallpaper_area(linked, wall_length_mm, ceiling_height_mm)

    return {
        "wall_lines": wall_lines,
        "wall_length_mm": wall_length_mm,
        "openings": linked,
        "dimensions": dimensions,
        "result": result
    }
