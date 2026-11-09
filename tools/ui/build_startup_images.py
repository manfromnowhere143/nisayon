"""Generate solid native iOS launch surfaces matching the document's ground.

These have no wordmark: the single HTML opening owns that mark and its position.
No animation, extra transition, font or image decode is added to the document.
"""

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIZES = [
    (320, 568, 2),
    (375, 667, 2),
    (414, 736, 3),
    (375, 812, 3),
    (390, 844, 3),
    (393, 852, 3),
    (402, 874, 3),
    (414, 896, 2),
    (414, 896, 3),
    (428, 926, 3),
    (430, 932, 3),
    (440, 956, 3),
    (768, 1024, 2),
    (820, 1180, 2),
    (834, 1194, 2),
    (1024, 1366, 2),
]


def png(width, height, rgb):
    def chunk(name, data):
        payload = name + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload))

    rows = (b"\0" + bytes(rgb) * width) * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 9))
        + chunk(b"IEND", b"")
    )


def main():
    output = ROOT / "apps/instrument/public/startup"
    output.mkdir(exist_ok=True)
    tags = []
    for width, height, ratio in SIZES:
        for orientation in ("portrait", "landscape"):
            w, h = (width, height) if orientation == "portrait" else (height, width)
            media = f"(device-width: {width}px) and (device-height: {height}px) and (-webkit-device-pixel-ratio: {ratio}) and (orientation: {orientation})"
            for theme, rgb in [("light", (244, 242, 236)), ("dark", (5, 5, 6))]:
                name = f"{w * ratio}-{h * ratio}-{theme}.png"
                (output / name).write_bytes(png(w * ratio, h * ratio, rgb))
                tags.append(
                    f'    <link rel="apple-touch-startup-image" href="/startup/{name}" media="{media} and (prefers-color-scheme: {theme})" />'
                )
    page = ROOT / "apps/instrument/index.html"
    text = page.read_text()
    start, end = "    <!-- native-launch-start -->", "    <!-- native-launch-end -->"
    block = start + "\n" + "\n".join(tags) + "\n" + end
    if start in text:
        first, rest = text.split(start, 1)
        text = first + block + rest.split(end, 1)[1]
    else:
        text = text.replace('    <link rel="manifest"', block + '\n    <link rel="manifest"', 1)
    page.write_text(text)


if __name__ == "__main__":
    main()
