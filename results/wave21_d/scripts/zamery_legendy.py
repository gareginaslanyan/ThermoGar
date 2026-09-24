"""21-D: legend text to legend fill contrast from frame pixels (frames 04, 17).

The legend is found in the dark frame, where its fill differs from the chart
background: the largest connected patch of the modal non-background colour
inside the chart image. Light and dark charts of one frame have the same
geometry (same figure size, same labels), so the dark box is used for the
light frame too. Inside the box (3 px inside the frame line):

* fill - the most frequent colour;
* text - the pixel of the text area with the largest WCAG 2.2 contrast to
  the fill, i.e. the core of the glyphs. The text area starts after the line
  samples: after the first gap of at least ``GAP_PX`` columns without ink
  (colour farther than ``INK_DELTA`` from the fill in some channel).

Charts are scaled by the browser (1460 -> 960 px), so glyph cores are
antialiased; the pixel figure is a lower bound of the nominal contrast.

The same is done for the 21-B frames (before the fix) for comparison.

Run from the w21b root:
    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_d\\scripts\\zamery_legendy.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

REPO_ROOT = Path(__file__).resolve().parents[3]
FRAMES = {
    "21-D": REPO_ROOT / "results" / "wave21_d" / "kadry",
    "21-B": REPO_ROOT / "results" / "wave21_b" / "kadry",
}
OUT = REPO_ROOT / "results" / "wave21_d" / "legenda_kontrast.json"
STEMS = ("04_raschety_temperaturnyi_diapazon", "17_diagrammy_troynaya")
THEMES = {"svet": "Light", "tyomn": "Dark"}
# Gap between the line samples and the text: handletextpad 0.8 em of 11 pt at
# 100 dpi, scaled 960/1460, is about 8 px.
GAP_PX = 5
INK_DELTA = 30
INSET_PX = 3


def luminance(rgb) -> float:
    def channel(value: float) -> float:
        value /= 255.0
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(float(v)) for v in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first, second) -> float:
    a, b = sorted((luminance(first), luminance(second)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def hex_of(rgb) -> str:
    return "#" + "".join(f"{int(v):02X}" for v in rgb)


def chart_rect(folder: Path, stem: str, theme: str) -> tuple[int, int, int, int]:
    """Chart image box; 21-B manifests have no rectangles, 21-D ones are used."""

    manifest = json.loads((FRAMES["21-D"] / "_manifest.json").read_text(encoding="utf-8"))
    for frame in manifest["frames"]:
        if frame["files"][0] == f"{stem}_{theme}.png":
            rect = frame["chartRects"][0]
            return tuple(
                int(round(v))
                for v in (rect["x"], rect["y"], rect["x"] + rect["width"], rect["y"] + rect["height"])
            )
    raise KeyError(stem)


def legend_box(chart: np.ndarray) -> tuple[int, int, int, int]:
    """Largest patch of one colour that is not the chart background (dark frame)."""

    pixels = chart.reshape(-1, 3)
    counts = Counter(map(tuple, pixels))
    background = counts.most_common(1)[0][0]
    best = None
    for colour, _count in counts.most_common(12)[1:]:
        mask = np.all(np.abs(chart.astype(int) - np.array(colour)) <= 2, axis=2)
        labels, number = ndimage.label(mask)
        if not number:
            continue
        sizes = ndimage.sum(mask, labels, range(1, number + 1))
        index = int(np.argmax(sizes)) + 1
        rows, cols = np.nonzero(labels == index)
        height = rows.max() - rows.min() + 1
        width = cols.max() - cols.min() + 1
        # A legend is a wide, not full-width box.
        if width < 80 or height < 20 or width > 0.8 * chart.shape[1]:
            continue
        if best is None or sizes[index - 1] > best[0]:
            best = (sizes[index - 1], (rows.min(), cols.min(), rows.max(), cols.max()), colour)
    if best is None:
        raise RuntimeError(f"no legend patch; background {hex_of(background)}")
    return best[1]


def measure(image_path: Path, box_in_chart, chart_box) -> dict:
    image = np.asarray(Image.open(image_path).convert("RGB"))
    x0, y0, x1, y1 = chart_box
    chart = image[y0:y1, x0:x1]
    top, left, bottom, right = box_in_chart
    inner = chart[top + INSET_PX:bottom - INSET_PX + 1, left + INSET_PX:right - INSET_PX + 1]
    fill = Counter(map(tuple, inner.reshape(-1, 3))).most_common(1)[0][0]
    ink = np.any(np.abs(inner.astype(int) - np.array(fill)) > INK_DELTA, axis=2).any(axis=0)
    first_ink = int(np.argmax(ink))
    text_left = None
    empty = 0
    for column in range(first_ink, ink.size):
        empty = empty + 1 if not ink[column] else 0
        if empty >= GAP_PX:
            text_left = column + 1
            break
    if text_left is None:
        raise RuntimeError(f"{image_path.name}: no gap between line samples and text")
    text_area = inner[:, text_left:].reshape(-1, 3)
    ratios = np.array([contrast(pixel, fill) for pixel in map(tuple, text_area)])
    core = tuple(text_area[int(np.argmax(ratios))])
    return {
        "legend_box_in_frame_px": [int(x0 + left), int(y0 + top), int(x0 + right), int(y0 + bottom)],
        "text_left_in_box_px": int(text_left + INSET_PX),
        "fill": hex_of(fill),
        "text_core": hex_of(core),
        "contrast_pixels": round(float(ratios.max()), 2),
    }


def main() -> None:
    result: dict = {"method": __doc__.split("Run from")[0].strip(), "frames": {}}
    for stem in STEMS:
        dark_box = chart_rect(FRAMES["21-D"], stem, "tyomn")
        dark_chart = np.asarray(
            Image.open(FRAMES["21-D"] / f"{stem}_tyomn.png").convert("RGB")
        )[dark_box[1]:dark_box[3], dark_box[0]:dark_box[2]]
        box = legend_box(dark_chart)
        for wave, folder in FRAMES.items():
            for slug, theme in THEMES.items():
                path = folder / f"{stem}_{slug}.png"
                entry = measure(path, box, chart_rect(folder, stem, slug))
                result["frames"][f"{wave} {path.name}"] = entry
                print(f"{wave} {path.name}: fill {entry['fill']}, text {entry['text_core']}, "
                      f"{entry['contrast_pixels']}:1", flush=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
