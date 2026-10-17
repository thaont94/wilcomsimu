import base64
import io
import json
import warnings
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
import numpy as np
from pyembroidery import EmbPattern, STITCH, JUMP, COLOR_CHANGE, END, write_dst, write_pes
from digitizer import RESOLUTION, objects_for_color

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
                   ignore_white: bool = Form(True), stitch_length: float = Form(2.5),
                   angle: float = Form(45), satin_width: float = Form(4),
                   object_types: str = Form("{}")):
    if not (10 <= width_mm <= 200 and 2 <= colors <= 12 and 0.4 <= spacing <= 2):
        raise HTTPException(422, "Kích thước 10–200 mm, số màu 2–12, khoảng hàng 0.4–2 mm.")
    if not (1 <= stitch_length <= 4 and 0 <= angle <= 180 and 1 <= satin_width <= 8):
        raise HTTPException(422, "Mũi tatami 1–4 mm, góc 0–180°, ngưỡng satin 1–8 mm.")
    try:
        overrides = json.loads(object_types)
        if not isinstance(overrides, dict) or len(overrides) > 500:
            raise ValueError()
        if any(v not in ("auto", "satin", "tatami") for v in overrides.values()):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(422, "Lựa chọn loại mũi không hợp lệ.")
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
    w = max(2, round(width_mm / RESOLUTION))
    h = max(2, round(height_mm / RESOLUTION))
    # Nearest sampling avoids inventing fringe colors around a flat-color logo.
    quantized = source.resize((w, h), Image.Resampling.NEAREST).quantize(colors=colors)
    pixels = np.asarray(quantized)
    palette = quantized.getpalette()
    pattern = EmbPattern()
    layers = []
    stitch_count = 0
    objects = []
    for label in sorted(np.unique(pixels).tolist()):
        rgb = palette[label * 3:label * 3 + 3]
        if ignore_white and min(rgb) >= 240:
            continue
        color = "#" + "".join(f"{v:02x}" for v in rgb)
        paths = []
        try:
            regions = list(objects_for_color(pixels == label, label, spacing, stitch_length,
                                            angle, satin_width, overrides))
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        if not regions:
            continue
        if layers:
            last = pattern.stitches[-1]
            pattern.add_stitch_absolute(COLOR_CHANGE, last[0], last[1])
        pattern.add_thread(color)
        for region in regions:
            if len(objects) >= 500:
                raise HTTPException(422, "Ảnh có quá nhiều vùng. Hãy giảm nhiễu hoặc số màu.")
            objects.append({**region, "color": color})
            for points in region["paths"]:
                pattern.add_stitch_absolute(JUMP, points[0][0] * 10, points[0][1] * 10)
                for x, py in points:
                    pattern.add_stitch_absolute(STITCH, x * 10, py * 10)
                stitch_count += len(points)
                if stitch_count > 100_000:
                    raise HTTPException(422, "Mẫu quá phức tạp; hãy tăng khoảng hàng hoặc giảm kích thước.")
                paths.append(points)
        layers.append({"color": color, "paths": paths})
    if not layers:
        raise HTTPException(422, "Không có vùng thêu. Thử tắt bỏ nền trắng.")
    pattern.add_stitch_absolute(END, pattern.stitches[-1][0], pattern.stitches[-1][1])
    exports = {}
    for extension, writer in (("dst", write_dst), ("pes", write_pes)):
        stream = io.BytesIO()
        writer(pattern, stream)
        exports[extension] = base64.b64encode(stream.getvalue()).decode("ascii")
    return {"width": width_mm, "height": round(height_mm, 2), "stitches": stitch_count,
            "layers": layers, "objects": objects, "exports": exports,
            "object_counts": {kind: sum(o["type"] == kind for o in objects) for kind in ("satin", "tatami")}}
