def normalize_bbox(px_x: float, px_y: float, px_w: float, px_h: float, image_w: float, image_h: float) -> tuple[float, float, float, float]:
    """
    Normalize bounding box coordinates to [0, 1] relative to image dimensions.
    Does not clamp the values; if they fall outside [0, 1] with a tolerance of 1e-6, raises ValueError.
    Raises ValueError if image dimensions are zero or negative.
    """
    if image_w <= 0 or image_h <= 0:
        raise ValueError("Image dimensions must be positive.")
        
    nx = px_x / image_w
    ny = px_y / image_h
    nw = px_w / image_w
    nh = px_h / image_h
    
    tol = 1e-6
    if not (-tol <= nx <= 1 + tol) or not (-tol <= ny <= 1 + tol) or \
       not (-tol <= nw <= 1 + tol) or not (-tol <= nh <= 1 + tol) or \
       not (-tol <= nx + nw <= 1 + tol) or not (-tol <= ny + nh <= 1 + tol):
        raise ValueError(f"Normalized box outside [0, 1]: ({nx}, {ny}, {nw}, {nh})")
        
    return nx, ny, nw, nh
