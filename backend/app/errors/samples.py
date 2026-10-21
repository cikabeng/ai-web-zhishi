"""示例报错截图（演示用）。

图片由服务端实时绘制，不依赖外部素材；前端「载入示例截图」会走同一条真实 OCR 链路。
"""

from __future__ import annotations

import io
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

SAMPLE_TEXT = """Traceback (most recent call last):
  File "demo.py", line 12, in <module>
    print(info['score'])
TypeError: 'NoneType' object is not subscriptable"""

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\consola.ttf",
    r"C:\Windows\Fonts\cour.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


@lru_cache(maxsize=1)
def sample_png() -> bytes:
    image = Image.new("RGB", (980, 260), (24, 26, 32))
    draw = ImageDraw.Draw(image)
    font = _load_font(26)
    draw.multiline_text((24, 24), SAMPLE_TEXT, font=font, fill=(230, 232, 240), spacing=10)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
