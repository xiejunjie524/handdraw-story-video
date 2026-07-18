#!/usr/bin/env python3
"""Derive aligned black ink line art from a colored hand-drawn illustration."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="approved color mother image")
    parser.add_argument("output", type=Path, help="output PNG/JPEG line image")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_bytes = np.fromfile(args.input, dtype=np.uint8)
    image = cv2.imdecode(source_bytes, cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"cannot read image: {args.input}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1].astype(np.float32)

    # Neutral dark strokes are likely ink. Suppress saturated pencil colors
    # without dilation so fine internal lines stay thin and separated.
    darkness = np.clip((218.0 - gray) / 185.0, 0.0, 1.0)
    neutrality = 1.0 - np.clip((saturation - 22.0) / 92.0, 0.0, 1.0)
    ink_strength = darkness * (neutrality**1.35)

    # Preserve genuinely black marks despite minor JPEG/color fringing.
    extreme_black = np.clip((72.0 - gray) / 42.0, 0.0, 1.0)
    ink_strength = np.maximum(ink_strength, extreme_black * 0.92)
    ink_strength = np.clip(ink_strength, 0.0, 1.0) ** 0.72
    ink_strength = cv2.GaussianBlur(ink_strength, (0, 0), 0.28)

    # Retain a whisper of paper texture while keeping contours clear on video.
    paper = np.clip(252.0 + (gray - 242.0) * 0.06, 248.0, 255.0)
    lineart = paper * (1.0 - ink_strength) + 12.0 * ink_strength
    lineart = np.clip(lineart, 0, 255).astype(np.uint8)
    output = cv2.cvtColor(lineart, cv2.COLOR_GRAY2BGR)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    extension = args.output.suffix.lower() or ".png"
    if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise SystemExit(f"unsupported output extension: {extension}")
    encoded_ok, encoded = cv2.imencode(extension, output)
    if not encoded_ok:
        raise SystemExit(f"cannot encode image: {args.output}")
    encoded.tofile(args.output)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
