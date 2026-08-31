import base64
from pathlib import Path

FONT_SIZE = 12.9
CHAR_W = round(FONT_SIZE * 0.600, 2)
LINE_H = round(FONT_SIZE * 1.25, 2)
FILL_LIGHT = "#1c1c1c"
FILL_DARK = "#d8d8d8"
DIM_LIGHT = "#8a8a8a"
DIM_DARK = "#8a8a8a"
RULE_LIGHT = "#d0d0d0"
RULE_DARK = "#3a3a3a"

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"


def xml_escape(s):
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def font_face_css(family, filename):
    path = FONT_DIR / filename
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        f"@font-face{{font-family:'{family}';"
        f"src:url(data:font/woff2;base64,{data}) format('woff2');"
        "font-weight:400;font-style:normal;}"
    )


def theme_style(selectors_fill, selectors_dim=None, selectors_rule=None):
    light = [f"{sel}{{fill:{FILL_LIGHT};}}" for sel in selectors_fill]
    if selectors_dim:
        light += [f"{sel}{{fill:{DIM_LIGHT};}}" for sel in selectors_dim]
    if selectors_rule:
        light += [f"{sel}{{stroke:{RULE_LIGHT};}}" for sel in selectors_rule]

    dark = [f"{sel}{{fill:{FILL_DARK};}}" for sel in selectors_fill]
    if selectors_dim:
        dark += [f"{sel}{{fill:{DIM_DARK};}}" for sel in selectors_dim]
    if selectors_rule:
        dark += [f"{sel}{{stroke:{RULE_DARK};}}" for sel in selectors_rule]

    return "".join(light) + "@media (prefers-color-scheme: dark){" + "".join(dark) + "}"


def svg_open(width, height, label):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{xml_escape(label)}">'
    )
