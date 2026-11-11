# -*- coding: utf-8 -*-
import os, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from PIL import Image, ImageDraw

os.makedirs("icons", exist_ok=True)
BG = (233, 30, 99)      # #e91e63
BG2 = (194, 24, 91)     # #c2185b
WHITE = (255, 255, 255)

def heart(draw, cx, cy, s, fill):
    # 两个圆 + 旋转方块拼爱心，s 为整体尺寸
    r = s * 0.28
    # 左圆、右圆
    draw.ellipse([cx - s*0.28 - r, cy - s*0.22 - r, cx - s*0.28 + r, cy - s*0.22 + r], fill=fill)
    draw.ellipse([cx + s*0.28 - r, cy - s*0.22 - r, cx + s*0.28 + r, cy - s*0.22 + r], fill=fill)
    # 下方菱形（旋转方块）
    pts = [(cx, cy + s*0.42), (cx - s*0.30, cy + s*0.02), (cx, cy - s*0.10), (cx + s*0.30, cy + s*0.02)]
    draw.polygon(pts, fill=fill)

def make(size, path):
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)
    # 简单渐变：竖向由 BG2 到 BG
    for y in range(size):
        t = y / size
        c = tuple(int(BG2[i] + (BG[i] - BG2[i]) * t) for i in range(3))
        draw.line([(0, y), (size, y)], fill=c)
    # 白色爱心居中
    heart(draw, size/2, size/2, size*0.55, WHITE)
    img.save(path, "PNG")
    print("saved", path, size)

make(192, "icons/icon-192.png")
make(512, "icons/icon-512.png")
