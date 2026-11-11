import zlib
import struct
import os

def create_png(width, height, r, g, b):
    # A simple RGBA PNG generator
    def chunk(tag, data):
        return struct.pack("!I", len(data)) + tag + data + struct.pack("!I", zlib.crc32(tag + data) & 0xffffffff)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 6, 0, 0, 0))

    raw = bytearray()
    center_x, center_y = width / 2.0, height / 2.0
    radius = min(width, height) * 0.42

    for y in range(height):
        raw.append(0)  # filter type 0
        for x in range(width):
            dist = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
            if dist <= radius:
                # Spider/Web purple-indigo gradient
                ratio = y / height
                pr = int(r * (1 - ratio * 0.3))
                pg = int(g * (1 - ratio * 0.2))
                pb = int(b)
                raw.extend([pr, pg, pb, 255])
            else:
                raw.extend([0, 0, 0, 0])

    idat = chunk(b"IDAT", zlib.compress(bytes(raw)))
    iend = chunk(b"IEND", b"")
    return header + ihdr + idat + iend

out_dir = "/home/epsilon/Projects/spiderRAG/extension/public/icons"
os.makedirs(out_dir, exist_ok=True)

for size in [16, 48, 128]:
    # Modern indigo accent: rgb(99, 102, 241)
    data = create_png(size, size, 99, 102, 241)
    with open(os.path.join(out_dir, f"icon-{size}.png"), "wb") as f:
        f.write(data)

print("Icons generated successfully!")
