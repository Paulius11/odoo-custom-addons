"""ESC/POS bytes for a receipt image, and sending them to a network printer."""

import io
import socket

from PIL import Image, ImageOps

# Printable width in dots at 203 dpi, the common thermal printer resolution
PAPER_DOTS = {"58": 384, "80": 576}
INIT = b"\x1b@"  # ESC @: reset the printer
CUT = b"\x1dVA\n"  # GS V A n: feed n dots, then cut
# ESC p m t1 t2 on both drawer pins (m = 0, 1): drawers are wired to either
DRAWER = b"\x1bp\x00\x19\x19\x1bp\x01\x19\x19"
RASTER = b"\x1dv0\x00"  # GS v 0: raster bit image, normal size
SLICE_ROWS = 255  # rows per raster command, small enough for any printer's buffer
MAX_PIXELS = 20_000_000  # a long receipt is ~576 x 5,000; refuse anything absurd
TIMEOUT = 5  # seconds to connect and send


def image_to_escpos(image_bytes, paper="80"):
    """ESC/POS commands that print the image centered on the paper, then cut."""
    image = Image.open(io.BytesIO(image_bytes))
    if image.width * image.height > MAX_PIXELS:
        raise ValueError("image too large")
    # A canvas export is RGBA with transparent margins: put it on white paper
    page = Image.new("RGBA", image.size, "white")
    page.alpha_composite(image.convert("RGBA"))
    image = page.convert("L")
    dots = PAPER_DOTS[paper]
    if image.width > dots:
        height = round(image.height * dots / image.width)
        image = image.resize((dots, height), Image.LANCZOS)
    paper_image = Image.new("L", (dots, image.height), 255)
    paper_image.paste(image, ((dots - image.width) // 2, 0))
    # Inverted 1-bit: bit 1 = black dot, as ESC/POS expects
    bits = ImageOps.invert(paper_image).convert("1").tobytes()
    row_bytes = dots // 8
    out = [INIT]
    for start in range(0, len(bits), row_bytes * SLICE_ROWS):
        chunk = bits[start : start + row_bytes * SLICE_ROWS]
        rows = len(chunk) // row_bytes
        out += [
            RASTER,
            row_bytes.to_bytes(2, "little"),
            rows.to_bytes(2, "little"),
            chunk,
        ]
    out.append(CUT)
    return b"".join(out)


def send(host, port, payload):
    """Open a TCP connection to the printer and write the payload (raises OSError)."""
    with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
        sock.sendall(payload)
