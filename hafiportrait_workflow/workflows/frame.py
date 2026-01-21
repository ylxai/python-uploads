from __future__ import annotations

from pathlib import Path

from PIL import Image

from ..models import Config


def crop_to_ratio(im: Image.Image, target_ratio: float) -> Image.Image:
    """Center-crop image to target ratio.

    Args:
        im: PIL Image
        target_ratio: width/height ratio (e.g., 1.49 for 1795:1205)

    Returns:
        Cropped image
    """

    w, h = im.size
    current_ratio = w / h

    if abs(current_ratio - target_ratio) < 0.01:
        # Already close enough
        return im

    if current_ratio > target_ratio:
        # Too wide, crop left/right
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        return im.crop((left, 0, left + new_w, h))
    else:
        # Too tall, crop top/bottom
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        return im.crop((0, top, w, top + new_h))


def apply_frame_landscape(photo_path: Path, frame_path: Path, output_path: Path) -> None:
    """Apply landscape frame to photo (Lightroom-style: minimal crop, preserve color).

    Strategy:
    - Resize photo maintaining aspect ratio to match frame size
    - Minimal center-crop if needed (typically < 1% of dimension)
    - Preserve ICC color profile
    - No distortion/stretch

    Args:
        photo_path: path to photo JPG
        frame_path: path to frame PNG (RGBA with transparent center)
        output_path: path to save result JPG
    """

    with Image.open(frame_path) as frame_im:
        frame_w, frame_h = frame_im.size
        target_ratio = frame_w / frame_h

        # Open photo
        with Image.open(photo_path) as photo_im:
            # Preserve ICC profile
            icc_profile = photo_im.info.get("icc_profile")
            
            # Convert to RGB if needed
            if photo_im.mode != "RGB":
                photo_im = photo_im.convert("RGB")

            # Crop to target ratio (minimal crop to avoid distortion)
            photo_cropped = crop_to_ratio(photo_im, target_ratio)

            # Resize to frame size
            photo_resized = photo_cropped.resize((frame_w, frame_h), Image.Resampling.LANCZOS)

            # Composite: photo as base, frame overlay on top
            if frame_im.mode == "RGBA":
                result = photo_resized.copy()
                result.paste(frame_im, (0, 0), frame_im)
            else:
                # Fallback if frame is not RGBA
                result = photo_resized

            # Save as JPG with ICC profile preserved
            save_kwargs = {"quality": 95, "optimize": True}
            if icc_profile:
                save_kwargs["icc_profile"] = icc_profile
            
            result.save(output_path, "JPEG", **save_kwargs)
