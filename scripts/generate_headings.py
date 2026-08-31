#!/usr/bin/env python3
from pathlib import Path

from svg_common import font_face_css, svg_open, theme_style, xml_escape

ROOT = Path(__file__).resolve().parent.parent
BODY_WIDTH = 696.6
FONT_SIZE = 15
CHAR_W = round(FONT_SIZE * 0.600, 2)
HEIGHT = 26


def render_heading(label, out_path):
    text_w = round(len(label) * CHAR_W, 2)
    rule_start = text_w + 10
    y_mid = round(HEIGHT / 2, 2)
    y_text = round(HEIGHT / 2 + FONT_SIZE * 0.32, 2)

    style = "<style>"
    style += font_face_css("headings", "headings.woff2")
    style += f"text{{font-family:'headings',ui-monospace,monospace;font-size:{FONT_SIZE}px;}}"
    style += theme_style([".label"], selectors_rule=[".rule"])
    style += "</style>"

    svg = [
        svg_open(BODY_WIDTH, HEIGHT, label),
        "<defs>", style, "</defs>",
        f'<line class="rule" x1="{rule_start}" y1="{y_mid}" x2="{BODY_WIDTH}" y2="{y_mid}" stroke-width="1"/>',
        f'<text class="label" x="0" y="{y_text}" xml:space="preserve">{xml_escape(label)}</text>',
        "</svg>",
    ]
    out_path.write_text("".join(svg), encoding="utf-8")


def main():
    labels = ["najee walker", "activity", "streaks", "languages", "year"]
    out_dir = ROOT
    for label in labels:
        slug = label.replace(" ", "-")
        render_heading(label, out_dir / f"h-{slug}.svg")
        print(f"wrote h-{slug}.svg")


if __name__ == "__main__":
    main()
