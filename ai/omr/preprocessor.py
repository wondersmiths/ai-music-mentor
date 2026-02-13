import cv2
import numpy as np


def load_image(path: str) -> np.ndarray:
    """Load an image (PNG/JPG) or the first page of a PDF and return as grayscale."""
    if path.lower().endswith(".pdf"):
        from pdf2image import convert_from_path

        pages = convert_from_path(path, first_page=1, last_page=1, dpi=300)
        img = np.array(pages[0])
        return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {path}")
    return img


def preprocess(image: np.ndarray) -> np.ndarray:
    """Binarize, denoise, and deskew an image for staff/note detection."""
    # Binarize with adaptive threshold
    binary = cv2.adaptiveThreshold(
        image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 10
    )

    # Denoise with morphological opening
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    # Deskew
    coords = np.column_stack(np.where(cleaned > 0))
    if len(coords) > 50:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) > 0.5:
            h, w = cleaned.shape
            center = (w // 2, h // 2)
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            cleaned = cv2.warpAffine(
                cleaned, matrix, (w, h), flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT, borderValue=0
            )

    return cleaned
