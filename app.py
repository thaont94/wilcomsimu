import base64
import io
import warnings
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
import numpy as np
from pyembroidery import EmbPattern, STITCH, JUMP, COLOR_CHANGE, END, write_dst, write_pes

app = FastAPI(title="Thread Studio")
Image.MAX_IMAGE_PIXELS = 16_000_000


@app.get("/")
def home():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/digitize")
async def digitize(image: UploadFile = File(...), width_mm: float = Form(100),
                   colors: int = Form(5), spacing: float = Form(0.6),
                   ignore_white: bool = Form(True)):
    if not (10 <= width_mm <= 200 and 2 <= colors <= 12 and 0.4 <= spacing <= 2):
        raise HTTPException(422, "Kích thước 10–200 mm, số màu 2–12, khoảng hàng 0.4–2 mm.")
    raw = await image.read(10_000_001)
    if len(raw) > 10_000_000:
        raise HTTPException(413, "Ảnh tối đa 10 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            source = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
            source.load()
            rgba = source.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            background.alpha_composite(rgba)
            source = background.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise HTTPException(400, "Không đọc được ảnh hoặc ảnh có quá nhiều điểm ảnh.")
    height_mm = width_mm * source.height / source.width
    if height_mm > 200:
        raise HTTPException(422, "Chiều cao vượt 200 mm. Hãy giảm chiều rộng.")
    # 0.5 mm sampling in X; the selected spacing controls the distance between rows.
    w = max(2, round(width_mm / 0.5))
    h = max(2, round(height_mm / spacing))
    quantized = source.resize((w, h)).quantize(colors=colors)
    pixels = np.asarray(quantized)
    palette = quantized.getpalette()
    pattern = EmbPattern()
    layers = []
    stitch_count = 0
    for label in sorted(np.unique(pixels).tolist()):
        rgb = palette[label * 3:label * 3 + 3]
        if ignore_white and min(rgb) >= 240:
            continue
        if layers:
            pattern.add_stitch_absolute(COLOR_CHANGE, 0, 0)
        color = "#" + "".join(f"{v:02x}" for v in rgb)
        pattern.add_thread(color)
        paths = []
        for row in range(h):
            indices = np.flatnonzero(pixels[row] == label)
            if not len(indices):
                continue
            groups = np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1)
            if row % 2:
                groups = groups[::-1]
            for group in groups:
                left = group[0] * width_mm / w
                right = (group[-1] + 1) * width_mm / w
                # Maximum stitch length 2.5 mm; isolated samples still form a stitch.
                xs = np.linspace(left, right, max(2, int(np.ceil((right-left) / 2.5)) + 1))
                if row % 2:
                    xs = xs[::-1]
                y = (row + 0.5) * height_mm / h
                points = [[round(float(x), 3), round(y, 3)] for x in xs]
                pattern.add_stitch_absolute(JUMP, points[0][0] * 10, y * 10)
                for x, py in points:
                    pattern.add_stitch_absolute(STITCH, x * 10, py * 10)
                stitch_count += len(points)
                if stitch_count > 100_000:
                    raise HTTPException(422, "Mẫu quá phức tạp; hãy tăng khoảng hàng hoặc giảm kích thước.")
                paths.append(points)
        layers.append({"color": color, "paths": paths})
    if not layers:
        raise HTTPException(422, "Không có vùng thêu. Thử tắt bỏ nền trắng.")
    pattern.add_stitch_absolute(END, 0, 0)
    exports = {}
    for extension, writer in (("dst", write_dst), ("pes", write_pes)):
        stream = io.BytesIO()
        writer(pattern, stream)
        exports[extension] = base64.b64encode(stream.getvalue()).decode("ascii")
    return {"width": width_mm, "height": round(height_mm, 2), "stitches": stitch_count,
            "layers": layers, "exports": exports}
