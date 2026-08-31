#!/usr/bin/env python3
import argparse
import base64
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rembg import remove, new_session

from svg_common import (
    CHAR_W,
    FILL_DARK,
    FILL_LIGHT,
    FONT_SIZE,
    LINE_H,
    font_face_css as _font_face_css,
    xml_escape,
)

RAMP = " .`:-=+*cs#%@"
ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"


def detect_face_box(bgr):
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5, minSize=(120, 120))
    if len(faces) == 0:
        h, w = bgr.shape[:2]
        side = min(h, w)
        return ((w - side) // 2, (h - side) // 2, side, side)
    return max(faces, key=lambda f: f[2] * f[3])


def crop_to_face(bgr, box):
    h, w = bgr.shape[:2]
    x, y, fw, fh = box
    top = max(0, int(y - fh * 0.70))
    bottom = min(h, int(y + fh * 1.80))
    left = max(0, int(x - fw * 0.55))
    right = min(w, int(x + fw * 1.55))
    return bgr[top:bottom, left:right]


def remove_background_to_white(bgr, session):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    pil_in = Image.fromarray(rgb)
    cut = remove(pil_in, session=session)
    white_bg = Image.new("RGBA", cut.size, (255, 255, 255, 255))
    white_bg.paste(cut, (0, 0), cut)
    return cv2.cvtColor(np.array(white_bg.convert("RGB")), cv2.COLOR_RGB2BGR)


def process_grayscale(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    smoothed = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    contrasted = clahe.apply(smoothed)
    normalised = contrasted.astype(np.float64) / 255.0
    darkened = np.power(normalised, 1.7) * 255.0
    return darkened.astype(np.uint8)


def to_ascii_rows(gray, cols):
    h, w = gray.shape[:2]
    rows = max(1, round(cols * (h / w) * 0.48))
    resized = cv2.resize(gray, (cols, rows), interpolation=cv2.INTER_AREA)
    n = len(RAMP) - 1
    idx = np.round((1.0 - resized.astype(np.float64) / 255.0) * n).astype(np.int32)
    idx = np.clip(idx, 0, n)
    lines = ["".join(RAMP[v] for v in row) for row in idx]
    return lines


def font_face_css():
    return _font_face_css("ramp", "ramp.woff2")


def render_svg(lines, out_path, stagger=0.09, wipe_dur=0.5):
    cols = max(len(l) for l in lines)
    rows = len(lines)
    row_w = round(cols * CHAR_W, 2)
    total_h = round(rows * LINE_H, 2)
    baseline_offset = round(LINE_H * 0.82, 2)

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {row_w} {total_h}" '
        f'width="{row_w}" height="{total_h}" role="img" aria-label="ASCII self-portrait">'
    )
    parts.append("<defs><style>")
    parts.append(font_face_css())
    parts.append(
        "text{font-family:'ramp',ui-monospace,'JetBrains Mono',monospace;"
        f"font-size:{FONT_SIZE}px;white-space:pre;}}"
    )
    parts.append(f".glyph{{fill:{FILL_LIGHT};}} .cursor{{fill:{FILL_LIGHT};}}")
    parts.append(
        "@media (prefers-color-scheme: dark){"
        f".glyph{{fill:{FILL_DARK};}} .cursor{{fill:{FILL_DARK};}}"
        "}"
    )
    for i in range(rows):
        parts.append(
            f'<clipPath id="clip{i}"><rect x="0" y="{round(i * LINE_H, 2)}" '
            f'width="0" height="{LINE_H}">'
            f'<animate attributeName="width" from="0" to="{row_w}" '
            f'dur="{wipe_dur}s" begin="{round(i * stagger, 3)}s" '
            f'fill="freeze" calcMode="linear"/></rect></clipPath>'
        )
    parts.append("</style></defs>")

    parts.append(f'<rect width="{row_w}" height="{total_h}" fill="transparent"/>')

    for i, line in enumerate(lines):
        y = round(i * LINE_H + baseline_offset, 2)
        parts.append(f'<g clip-path="url(#clip{i})">')
        parts.append(f'<text class="glyph" x="0" y="{y}" xml:space="preserve">{xml_escape(line)}</text>')
        parts.append("</g>")
        begin = round(i * stagger, 3)
        parts.append(
            f'<rect class="cursor" x="0" y="{round(i * LINE_H, 2)}" '
            f'width="{round(CHAR_W * 0.6, 2)}" height="{round(LINE_H * 0.82, 2)}">'
            f'<animate attributeName="x" from="0" to="{row_w}" dur="{wipe_dur}s" '
            f'begin="{begin}s" fill="freeze" calcMode="linear"/>'
            f'<animate attributeName="opacity" from="1" to="0" dur="0.15s" '
            f'begin="{round(begin + wipe_dur, 3)}s" fill="freeze"/>'
            "</rect>"
        )

    parts.append("</svg>")
    out_path.write_text("".join(parts), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "portrait.svg")
    ap.add_argument("--cols", type=int, default=90)
    ap.add_argument("--dump-txt", type=Path, default=None)
    args = ap.parse_args()

    bgr = cv2.imread(str(args.input))
    if bgr is None:
        sys.exit(f"could not read {args.input}")

    box = detect_face_box(bgr)
    cropped = crop_to_face(bgr, box)

    session = new_session("u2net")
    white_bg = remove_background_to_white(cropped, session)

    gray = process_grayscale(white_bg)
    lines = to_ascii_rows(gray, args.cols)

    if args.dump_txt:
        args.dump_txt.write_text("\n".join(lines), encoding="utf-8")

    render_svg(lines, args.out)
    print(f"wrote {args.out} ({len(lines)} rows x {args.cols} cols)")


if __name__ == "__main__":
    main()
