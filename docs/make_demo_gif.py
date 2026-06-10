#!/usr/bin/env python3
"""
Generate an illustrative animated demo of the kawaii face for the README.

This is a stylised mock-up (not a screen capture) drawn with Pillow, matching
the component's palette: white eyeballs, cyan irises, pink blush, heart eyes,
red mouth, on a dark "screen" background. It cycles through several emotions
with smooth transitions and blinks.

Run:  python3 docs/make_demo_gif.py
Out:  docs/kawaii_face_demo.gif
"""
import math
import os
from PIL import Image, ImageDraw, ImageFont

SS = 3                      # supersampling for anti-aliasing
W = H = 300                 # final frame size
RW, RH = W * SS, H * SS

BG       = (11, 14, 19)     # dark screen
FRAME    = (28, 35, 49)     # faint screen border
EYE      = (250, 250, 250)  # white eyeball
IRIS     = (50, 180, 255)   # cyan iris
PUPIL    = (15, 30, 55)
BROW     = (60, 70, 85)
MOUTH    = (210, 70, 95)
HEART    = (255, 77, 121)
BLUSH    = (255, 150, 180)
CAP      = (150, 165, 185)

try:
    FONT = ImageFont.truetype("DejaVuSans.ttf", 17 * SS)
except Exception:
    FONT = ImageFont.load_default(size=17 * SS)


def lerp(a, b, t):
    return a + (b - a) * t


# --- Emotion keyframes (numeric fields are interpolated) --------------------
def kf(name, eo=0.88, eo_r=None, blush=0.0, brow_y=0.0, tilt=0.0,
       mouth=("smile", 0.15), hearts=False, pdx=0.0, pdy=0.0):
    return dict(name=name, eo=eo, eo_r=eo if eo_r is None else eo_r, blush=blush,
                brow_y=brow_y, tilt=tilt, mouth=mouth, hearts=hearts, pdx=pdx, pdy=pdy)

KEYS = [
    kf("neutral",   eo=0.86, mouth=("smile", 0.15)),
    kf("happy",     eo=0.96, blush=0.7,  brow_y=0.10, mouth=("smile", 0.85)),
    kf("surprised", eo=1.00, brow_y=0.55, mouth=("open", 0.55), pdy=-0.1),
    kf("love",      eo=0.00, blush=1.0,  mouth=("smile", 0.9), hearts=True),
    kf("wink",      eo=0.96, eo_r=0.05, blush=0.5, mouth=("smile", 0.6)),
    kf("sad",       eo=0.55, tilt=-0.8,  mouth=("frown", 0.6), pdy=0.25),
    kf("angry",     eo=0.80, brow_y=-0.15, tilt=0.9, mouth=("frown", 0.35)),
    kf("cool",      eo=0.42, mouth=("smile", 0.3), pdx=0.35),
]

HOLD, TRANS = 6, 6
BLINK_ON = {"neutral", "happy", "cool"}   # emotions that blink during hold


def blink_scale(i, n):
    """Eye-openness multiplier producing one blink within n hold frames."""
    c = n // 2
    d = abs(i - c)
    if d == 0:
        return 0.08
    if d == 1:
        return 0.5
    return 1.0


def build_timeline():
    frames = []
    n = len(KEYS)
    for s in range(n):
        a, b = KEYS[s], KEYS[(s + 1) % n]
        do_blink = a["name"] in BLINK_ON
        for i in range(HOLD):
            f = dict(a)
            drift = math.sin(i / HOLD * math.pi * 2) * 0.12
            f["pdx"] = a["pdx"] + drift
            if do_blink:
                bs = blink_scale(i, HOLD)
                f["eo"], f["eo_r"] = a["eo"] * bs, a["eo_r"] * bs
            frames.append(f)
        for i in range(TRANS):
            t = (i + 1) / TRANS
            te = t * t * (3 - 2 * t)   # smoothstep
            f = dict(name=b["name"] if t >= 0.5 else a["name"],
                     hearts=b["hearts"] if t >= 0.5 else a["hearts"],
                     mouth=b["mouth"] if t >= 0.5 else a["mouth"])
            for k in ("eo", "eo_r", "blush", "brow_y", "tilt", "pdx", "pdy"):
                f[k] = lerp(a[k], b[k], te)
            ma = lerp(a["mouth"][1], b["mouth"][1], te)
            f["mouth"] = (f["mouth"][0], ma)
            frames.append(f)
    return frames


def draw_eye(d, cx, cy, ew, eh, openv, pdx, pdy, hearts):
    if hearts:
        s = ew * 0.95
        draw_heart(d, cx, cy, s)
        return
    h = max(eh * openv, eh * 0.06)
    if openv < 0.16:                      # closed -> cute upward arc
        bbox = [cx - ew / 2, cy - eh * 0.30, cx + ew / 2, cy + eh * 0.30]
        d.arc(bbox, start=200, end=340, fill=EYE, width=int(7 * SS))
        return
    d.rounded_rectangle([cx - ew / 2, cy - h / 2, cx + ew / 2, cy + h / 2],
                        radius=ew * 0.45, fill=EYE)
    ir = min(ew, h) * 0.40
    ix = cx + pdx * ew * 0.22
    iy = cy + pdy * h * 0.22
    d.ellipse([ix - ir, iy - ir, ix + ir, iy + ir], fill=IRIS)
    pr = ir * 0.5
    d.ellipse([ix - pr, iy - pr, ix + pr, iy + pr], fill=PUPIL)
    hr = ir * 0.28
    d.ellipse([ix - ir * 0.35 - hr, iy - ir * 0.35 - hr,
               ix - ir * 0.35 + hr, iy - ir * 0.35 + hr], fill=(255, 255, 255))


def draw_heart(d, cx, cy, s):
    r = s * 0.30
    d.ellipse([cx - 0.62 * s, cy - 0.55 * s, cx - 0.62 * s + 2 * r,
               cy - 0.55 * s + 2 * r], fill=HEART)
    d.ellipse([cx + 0.02 * s, cy - 0.55 * s, cx + 0.02 * s + 2 * r,
               cy - 0.55 * s + 2 * r], fill=HEART)
    d.polygon([(cx - 0.66 * s, cy - 0.18 * s), (cx + 0.66 * s, cy - 0.18 * s),
               (cx, cy + 0.62 * s)], fill=HEART)
    hr = s * 0.12
    d.ellipse([cx - 0.42 * s, cy - 0.42 * s, cx - 0.42 * s + hr,
               cy - 0.42 * s + hr], fill=(255, 210, 225))


def bezier(p0, p1, p2, steps=24):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        pts.append((x, y))
    return pts


def draw_mouth(d, cx, cy, kind, amt):
    half = RW * 0.11
    w = int(7 * SS)
    if kind == "open":
        rw_, rh_ = RW * 0.07 * (0.6 + amt), RH * 0.06 * (0.7 + amt)
        d.ellipse([cx - rw_, cy - rh_, cx + rw_, cy + rh_], fill=(150, 40, 60))
        d.ellipse([cx - rw_ * 0.45, cy + rh_ * 0.1, cx + rw_ * 0.45,
                   cy + rh_ * 0.9], fill=HEART)        # little tongue
        return
    depth = RH * 0.085 * amt
    if kind == "frown":
        pts = bezier((cx - half, cy + depth * 0.6), (cx, cy - depth),
                     (cx + half, cy + depth * 0.6))
    else:  # smile
        pts = bezier((cx - half, cy - depth * 0.4), (cx, cy + depth),
                     (cx + half, cy + depth * 0.4))
    d.line(pts, fill=MOUTH, width=w, joint="curve")
    for e in (pts[0], pts[-1]):           # round caps
        d.ellipse([e[0] - w / 2, e[1] - w / 2, e[0] + w / 2, e[1] + w / 2], fill=MOUTH)


def draw_brow(d, cx, ytop, tilt, raise_):
    bw = RW * 0.085
    y = ytop - raise_ * RH * 0.05
    inner = y + tilt * RH * 0.045
    outer = y - tilt * RH * 0.015
    # cx is eye centre; inner end is toward the nose
    sign = 1 if cx > RW / 2 else -1
    x_in = cx - sign * bw
    x_out = cx + sign * bw
    d.line([(x_in, inner), (x_out, outer)], fill=BROW, width=int(6 * SS),
           joint="curve")


def render(f):
    base = Image.new("RGB", (RW, RH), BG)
    d = ImageDraw.Draw(base, "RGBA")
    inset = 8 * SS
    d.rounded_rectangle([inset, inset, RW - inset, RH - inset],
                        radius=26 * SS, outline=FRAME, width=2 * SS)

    cx = RW / 2
    eye_y = RH * 0.42
    dx = RW * 0.18
    ew, eh = RW * 0.17, RH * 0.21

    if f["blush"] > 0.01:                  # pink blush dots on the cheeks
        a = int(210 * f["blush"])
        for sgn in (-1, 1):
            bx = cx + sgn * dx * 1.2
            by = eye_y + eh * 1.0
            d.ellipse([bx - ew * 0.40, by - eh * 0.20, bx + ew * 0.40,
                       by + eh * 0.20], fill=(*BLUSH, a))

    if not f["hearts"]:
        draw_brow(d, cx - dx, eye_y - eh * 0.75, f["tilt"], f["brow_y"])
        draw_brow(d, cx + dx, eye_y - eh * 0.75, f["tilt"], f["brow_y"])

    draw_eye(d, cx - dx, eye_y, ew, eh, f["eo"],   f["pdx"], f["pdy"], f["hearts"])
    draw_eye(d, cx + dx, eye_y, ew, eh, f["eo_r"], f["pdx"], f["pdy"], f["hearts"])

    draw_mouth(d, cx, RH * 0.68, f["mouth"][0], f["mouth"][1])

    cap = f["name"]
    tb = d.textbbox((0, 0), cap, font=FONT)
    d.text(((RW - (tb[2] - tb[0])) / 2, RH * 0.86), cap, font=FONT, fill=CAP)

    return base.resize((W, H), Image.LANCZOS)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "kawaii_face_demo.gif")
    frames = [render(f) for f in build_timeline()]
    pal = [im.convert("P", palette=Image.ADAPTIVE, colors=128) for im in frames]
    pal[0].save(out, save_all=True, append_images=pal[1:], loop=0,
                duration=80, disposal=2, optimize=True)
    print("wrote", out, os.path.getsize(out) // 1024, "KB,", len(frames), "frames")


if __name__ == "__main__":
    main()
