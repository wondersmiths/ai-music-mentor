import cv2
import numpy as np


def detect_staff_lines(image: np.ndarray) -> list[int]:
    """Find horizontal staff lines via horizontal projection."""
    h, w = image.shape
    projection = np.sum(image, axis=1) / 255

    # Staff lines have high horizontal density
    threshold = w * 0.3
    candidates = np.where(projection > threshold)[0]

    if len(candidates) == 0:
        return []

    # Group adjacent rows into single line positions
    lines: list[int] = []
    group_start = candidates[0]
    for i in range(1, len(candidates)):
        if candidates[i] - candidates[i - 1] > 2:
            lines.append(int((group_start + candidates[i - 1]) // 2))
            group_start = candidates[i]
    lines.append(int((group_start + candidates[-1]) // 2))

    return lines


def detect_noteheads(
    image: np.ndarray, staff_lines: list[int]
) -> list[dict]:
    """Find filled/open noteheads using contour analysis."""
    if not staff_lines:
        return []

    # Remove staff lines to isolate noteheads
    cleaned = image.copy()
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
    staff_mask = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, h_kernel)
    cleaned = cv2.subtract(cleaned, staff_mask)

    # Dilate slightly to reconnect broken noteheads
    kernel = np.ones((3, 3), np.uint8)
    cleaned = cv2.dilate(cleaned, kernel, iterations=1)

    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detections: list[dict] = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        aspect = bw / bh if bh > 0 else 0

        # Filter: noteheads are roughly elliptical, wider than tall
        if area < 50 or bw < 5 or bh < 5:
            continue
        if aspect < 0.5 or aspect > 3.0:
            continue

        # Check if filled (high pixel density) or open
        roi = image[y : y + bh, x : x + bw]
        fill_ratio = np.sum(roi > 0) / (bw * bh) if (bw * bh) > 0 else 0
        is_filled = fill_ratio > 0.5

        # Check for stem (vertical line above or below)
        stem_region_above = image[max(0, y - bh * 3) : y, x : x + bw]
        stem_region_below = image[y + bh : min(image.shape[0], y + bh * 4), x : x + bw]
        has_stem = (
            np.sum(stem_region_above > 0) > bw * bh * 0.3
            or np.sum(stem_region_below > 0) > bw * bh * 0.3
        )

        # Check for flag (small region at stem end)
        has_flag = False
        if has_stem:
            flag_region = image[max(0, y - bh * 3) : max(0, y - bh * 2), x + bw : x + bw * 2]
            if flag_region.size > 0:
                has_flag = np.sum(flag_region > 0) > flag_region.size * 0.15

        detections.append({
            "x": x,
            "y": y + bh // 2,
            "width": bw,
            "height": bh,
            "area": area,
            "is_filled": is_filled,
            "has_stem": has_stem,
            "has_flag": has_flag,
            "has_beam": False,  # beam detection requires cross-note analysis
            "contour": contour,
        })

    # Sort by x position (left to right)
    detections.sort(key=lambda d: d["x"])
    return detections


def estimate_confidence(detections: list[dict]) -> float:
    """Heuristic confidence (0-1) based on detection count and spacing regularity."""
    if len(detections) < 2:
        return 0.0

    # More notes generally means better detection (up to a point)
    count_score = min(len(detections) / 8.0, 1.0)

    # Check spacing regularity
    xs = [d["x"] for d in detections]
    spacings = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
    if spacings:
        mean_spacing = np.mean(spacings)
        std_spacing = np.std(spacings)
        regularity = 1.0 - min(std_spacing / (mean_spacing + 1e-6), 1.0)
    else:
        regularity = 0.0

    return round(0.5 * count_score + 0.5 * regularity, 3)
