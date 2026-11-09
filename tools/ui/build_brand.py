"""Render the source SVG mark at browser, search, touch, and sharing sizes."""

import json
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "apps/instrument/public"
MARK = re.search(
    r'BRAND_PATH = "([^"]+)"', (ROOT / "apps/instrument/src/ui/BrandMark.tsx").read_text()
)[1]


def svg(body, width=96, height=96):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">{body}</svg>\n'


def path(color, stroke=8):
    return f'<path d="{MARK}" fill="none" stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round"/>'


def render(source, target, size=None):
    command = ["rsvg-convert", str(source), "-o", str(target)]
    if size:
        command += ["-w", str(size), "-h", str(size)]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    brand = PUBLIC / "brand"
    brand.mkdir(parents=True, exist_ok=True)
    (brand / "nisayon-mark.svg").write_text(svg(path("#17171a")))
    (brand / "nisayon-mark-light.svg").write_text(svg(path("#f2f2ee")))
    favicon = PUBLIC / "favicon.svg"
    favicon.write_text(
        svg('<rect width="96" height="96" rx="21" fill="#08090b"/>' + path("#f2f2ee", 10))
    )
    for size in (16, 32, 48, 96, 192, 512):
        render(favicon, PUBLIC / f"favicon-{size}.png", size)
    # PNG-backed ICO directory; exact source pixels, no image-library dependency.
    images = [(PUBLIC / f"favicon-{size}.png").read_bytes() for size in (16, 32, 48)]
    offset = 6 + 16 * len(images)
    table = b""
    for size, image in zip((16, 32, 48), images, strict=True):
        table += struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(image), offset)
        offset += len(image)
    (PUBLIC / "favicon.ico").write_bytes(
        struct.pack("<HHH", 0, 1, len(images)) + table + b"".join(images)
    )
    touch = brand / "touch-source.svg"
    touch.write_text(svg('<rect width="96" height="96" fill="#08090b"/>' + path("#f2f2ee", 8)))
    render(touch, PUBLIC / "apple-touch-icon.png", 180)
    mask = brand / "maskable-source.svg"
    mask.write_text(
        svg(
            '<rect width="96" height="96" fill="#08090b"/><g transform="translate(7.2 7.2) scale(.85)">'
            + path("#f2f2ee", 8)
            + "</g>"
        )
    )
    render(mask, PUBLIC / "icon-maskable-512.png", 512)
    (PUBLIC / "site.webmanifest").write_text(
        json.dumps(
            {
                "name": "Nisayon",
                "short_name": "Nisayon",
                "description": "An experiment engine for physical AI.",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#08090b",
                "theme_color": "#08090b",
                "icons": [
                    {"src": f"/favicon-{size}.png", "sizes": f"{size}x{size}", "type": "image/png"}
                    for size in (192, 512)
                ]
                + [
                    {
                        "src": "/icon-maskable-512.png",
                        "sizes": "512x512",
                        "type": "image/png",
                        "purpose": "maskable",
                    }
                ],
            },
            indent=2,
        )
        + "\n"
    )
    share = brand / "nisayon-share.svg"
    share.write_text(
        svg(
            '<rect width="1200" height="630" fill="#08090b"/><g transform="translate(100 186) scale(2.7)">'
            + path("#f2f2ee")
            + '</g><g font-family="Helvetica,Arial,sans-serif" fill="#f2f2ee"><text x="395" y="335" font-size="100" font-weight="500" letter-spacing="-5">Nisayon</text><text x="402" y="392" font-size="25" fill="#a5a6aa">An experiment engine for physical AI.</text></g><path d="M108 530H1092" stroke="#292a2d"/><text x="110" y="566" font-family="Helvetica,Arial,sans-serif" font-size="16" fill="#8b8c90" letter-spacing="2">EXPERIMENT · EVIDENCE · CONFIRMATION</text>',
            1200,
            630,
        )
    )
    render(share, brand / "nisayon-share.png")
    print("Rendered vector mark, favicon sizes, touch icon, manifest, and share image.")
