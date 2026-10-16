"""CV gap detector for Aliyun slide-puzzle — cv2 Sobel-x gradient template match.
Self-contained, fast (5-15ms), no external models or network needed.
"""
import cv2
import numpy as np

def _piece_geometry(shadow_bytes: bytes) -> dict | None:
    if not shadow_bytes:
        return None
    sh = cv2.imdecode(np.frombuffer(shadow_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
    if sh is None:
        return None
    if sh.ndim == 3 and sh.shape[2] == 4:
        alpha = sh[:, :, 3]
    else:
        alpha = (cv2.cvtColor(sh, cv2.COLOR_BGR2GRAY) > 10).astype(np.uint8) * 255
    ys, xs = np.where(alpha > 30)
    if len(xs) == 0:
        return None
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    return {"y0": y0, "y1": y1, "x0": x0, "x1": x1, "pw": x1 - x0, "alpha": alpha}

def _piece_band(alpha: np.ndarray, y0: int, y1: int, x0: int, x1: int):
    band = alpha[y0:y1 + 1, x0:x1 + 1]
    return (band > 30).astype(np.float32) * 255

def detect_gap_x(back_bytes: bytes, shadow_bytes: bytes) -> dict:
    """Detect the gap left-edge x.
    1. YOLO ONNX (high accuracy trained detector)
    2. cv2 Sobel-x template matching (fallback)
    """
    # Stage 1: YOLO ONNX with Sobel contour refinement
    try:
        from .gap_yolo import detect_gap_yolo
        y = detect_gap_yolo(back_bytes, shadow_bytes)
        if y is not None:
            geo = _piece_geometry(shadow_bytes)
            if geo:
                # Refine YOLO gap using cv2 Sobel template match within ±18px window
                try:
                    back = cv2.imdecode(np.frombuffer(back_bytes, np.uint8), cv2.IMREAD_COLOR)
                    if back is not None:
                        gray = cv2.cvtColor(back, cv2.COLOR_BGR2GRAY)
                        gx = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
                        y0, y1, x0, pw = geo["y0"], geo["y1"], geo["x0"], geo["pw"]
                        alpha = geo["alpha"]
                        shp = _piece_band(alpha, y0, y1, x0, x0 + pw)
                        tgx = np.abs(cv2.Sobel(shp, cv2.CV_32F, 1, 0, ksize=3))
                        band = gx[y0:y1 + 1, :].astype(np.float32)

                        res = cv2.matchTemplate(band, tgx, cv2.TM_CCOEFF_NORMED)
                        yolo_x = y["gap_x"]
                        win_min = max(0, yolo_x - 18)
                        win_max = min(res.shape[1], yolo_x + 18)
                        sub_res = res[:, win_min:win_max]
                        _, maxv, _, maxloc = cv2.minMaxLoc(sub_res)
                        if maxv > 0.25:
                            refined_x = win_min + maxloc[0]
                            y["gap_x"] = refined_x
                            y["method"] = "yolo+sobel"
                except Exception:
                    pass

                y.setdefault("piece_x0", geo["x0"])
                y["piece_w"] = geo["pw"]
                y["slide_dist"] = y["gap_x"] - geo["x0"]
            return y
    except Exception:
        pass

    # Stage 2: cv2 Sobel
    return _detect_gap_cv(back_bytes, shadow_bytes)

def _detect_gap_cv(back_bytes: bytes, shadow_bytes: bytes) -> dict:
    geo = _piece_geometry(shadow_bytes)
    if geo is None:
        return {"gap_x": 0, "piece_w": 0, "method": "cv2-fail"}
    if not back_bytes:
        return {"gap_x": 0, "piece_w": 0, "method": "cv2-fail"}

    back = cv2.imdecode(np.frombuffer(back_bytes, np.uint8), cv2.IMREAD_COLOR)
    if back is None:
        return {"gap_x": 0, "piece_w": 0, "method": "cv2-fail"}

    y0, y1, x0, pw = geo["y0"], geo["y1"], geo["x0"], geo["pw"]
    alpha = geo["alpha"]

    gray = cv2.cvtColor(back, cv2.COLOR_BGR2GRAY)
    gx = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    shp = _piece_band(alpha, y0, y1, x0, x0 + pw)
    tgx = np.abs(cv2.Sobel(shp, cv2.CV_32F, 1, 0, ksize=3))
    band = gx[y0:y1 + 1, :].astype(np.float32)

    res = cv2.matchTemplate(band, tgx, cv2.TM_CCOEFF_NORMED)
    res[:, :x0 + pw] = -1  # gap is always right of the start piece
    _, maxv, _, maxloc = cv2.minMaxLoc(res)
    gap_x = int(maxloc[0])

    return {
        "gap_x": gap_x,
        "piece_x0": x0,
        "piece_w": pw,
        "back_w": int(back.shape[1]),
        "slide_dist": gap_x - x0,
        "confidence": round(float(maxv), 3),
        "method": "cv2-sobel"
    }
