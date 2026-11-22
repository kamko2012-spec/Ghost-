"""Render a 60-second Krasue (ผีกระสือ) horror clip: procedural visuals + synthesized ambience.

Usage: python3 render.py [output.mp4]
"""
import math
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, DUR = 1280, 720, 24, 60
N = FPS * DUR
SR = 44100
FONT = "/usr/share/fonts/opentype/tlwg/Loma-Bold.otf"
OUT = sys.argv[1] if len(sys.argv) > 1 else "krasue.mp4"
rng = np.random.default_rng(7)
random.seed(7)

# ---------------------------------------------------------------- script
# (start, end, text)
SUBS = [
    (1.0, 7.5, "ผีกระสือ"),
    (8.5, 13.0, "หมู่บ้านเล็กๆ ริมทุ่งนา ทางภาคอีสาน"),
    (13.3, 18.0, "ยายเตือนหลานไว้ข้อเดียว... \"อย่าตากผ้าทิ้งไว้นอกบ้านตอนกลางคืน\""),
    (19.0, 24.0, "คืนนั้น ตีสองสิบเจ็ดนาที"),
    (24.3, 30.0, "มีแสงสีเขียว ลอยต่ำๆ อยู่เหนือทุ่งนา"),
    (31.0, 36.0, "มันลอยใกล้เข้ามา... ช้าๆ"),
    (36.3, 41.5, "เสียงจิ้งหรีดเงียบลงพร้อมกัน... ทั้งทุ่ง"),
    (46.0, 50.0, "ใบหน้าผู้หญิง... ไม่มีร่างกาย"),
    (50.8, 55.5, "เช้าวันต่อมา ผ้าถุงบนราว... เปียกชุ่ม ทั้งที่ฝนไม่ได้ตก"),
    (56.0, 59.6, "คืนนี้... คุณเก็บผ้าเข้าบ้านแล้วหรือยัง?"),
]
CLOCK = (19.0, 24.0, "02:17")

# ---------------------------------------------------------------- helpers
def smooth(a, b, t):
    if t <= a:
        return 0.0
    if t >= b:
        return 1.0
    x = (t - a) / (b - a)
    return x * x * (3 - 2 * x)


def env(t, a, b, fade=0.6):
    return smooth(a, a + fade, t) * (1 - smooth(b - fade, b, t))


def vgrad(top, bottom):
    y = np.linspace(0, 1, H)[:, None, None]
    g = np.array(top, float) * (1 - y) + np.array(bottom, float) * y
    return np.broadcast_to(g, (H, W, 3)).copy()


def fog_tex(scale, seed):
    r = np.random.default_rng(seed)
    small = r.random((H // scale + 3, 2 * W // scale))
    small = np.concatenate([small, small[:, :3]], axis=1)  # wrap so the scroll is seamless
    img = Image.fromarray((small * 255).astype(np.uint8)).resize(
        (small.shape[1] * scale, small.shape[0] * scale), Image.BICUBIC).filter(ImageFilter.GaussianBlur(scale * 0.6))
    return np.asarray(img, float)[:H, :2 * W] / 255.0


FOG1 = fog_tex(96, 1)
FOG2 = fog_tex(48, 2)


def fog(t, strength, tint=(150, 170, 175)):
    o1 = int(t * 18) % W
    o2 = int(t * 35) % W
    f = 0.6 * FOG1[:, o1:o1 + W] + 0.4 * FOG2[:, o2:o2 + W]
    ymask = np.linspace(0.3, 1.0, H)[:, None]
    f = (f * ymask * strength)[..., None]
    return f * np.array(tint, float)


# ---------------------------------------------------------------- static layers
def draw_stilt_house(d, x, base, w, h, col):
    d.rectangle([x, base - h * 0.45, x + w, base - h * 0.15], fill=col)
    d.polygon([(x - w * 0.12, base - h * 0.45), (x + w / 2, base - h), (x + w * 1.12, base - h * 0.45)], fill=col)
    for px in np.linspace(x + 4, x + w - 8, 5):
        d.rectangle([px, base - h * 0.15, px + 5, base], fill=col)


def village_layer():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    hz = 470
    # distant tree line
    pts = [(0, hz)]
    for x in range(0, W + 20, 20):
        pts.append((x, hz - 25 - 18 * math.sin(x * 0.013) - random.random() * 14))
    pts.append((W, hz))
    d.polygon(pts, fill=(12, 20, 22, 255))
    # palms
    for px in (140, 980, 1150):
        d.line([(px, hz), (px + 8, hz - 150)], fill=(8, 12, 14, 255), width=6)
        for a in range(0, 360, 40):
            ang = math.radians(a)
            d.line([(px + 8, hz - 150), (px + 8 + 60 * math.cos(ang), hz - 150 + 30 * math.sin(ang) + 18)],
                   fill=(8, 12, 14, 255), width=4)
    # ground
    d.rectangle([0, hz, W, H], fill=(10, 16, 16, 255))
    # houses
    draw_stilt_house(d, 230, hz + 40, 170, 190, (6, 9, 10, 255))
    draw_stilt_house(d, 760, hz + 30, 130, 150, (7, 10, 11, 255))
    # lit window in house 1
    d.rectangle([290, hz + 40 - 190 * 0.40, 315, hz + 40 - 190 * 0.22], fill=(150, 110, 50, 255))
    # clothesline
    d.line([(450, hz + 60), (450, hz - 40)], fill=(5, 7, 8, 255), width=4)
    d.line([(690, hz + 60), (690, hz - 40)], fill=(5, 7, 8, 255), width=4)
    d.line([(450, hz - 36), (690, hz - 30)], fill=(30, 34, 36, 255), width=2)
    # sarongs hanging
    for i, cx in enumerate((485, 545, 615)):
        col = [(70, 30, 40, 255), (40, 50, 70, 255), (60, 55, 35, 255)][i]
        d.polygon([(cx, hz - 35), (cx + 45, hz - 34), (cx + 42, hz + 30), (cx + 3, hz + 32)], fill=col)
    return img


def field_layer():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    hz = 400
    pts = [(0, hz)] + [(x, hz - 12 - 10 * math.sin(x * 0.02) - random.random() * 8) for x in range(0, W + 20, 16)] + [(W, hz)]
    d.polygon(pts, fill=(10, 18, 20, 255))
    d.rectangle([0, hz, W, H], fill=(9, 17, 15, 255))
    # rice paddy dykes in perspective
    for i in range(1, 9):
        y = hz + (H - hz) * (i / 9) ** 1.6
        d.line([(0, y), (W, y)], fill=(16, 26, 22, 255), width=1 + i // 3)
    for k in range(-8, 9):
        d.line([(W / 2 + k * 30, hz), (W / 2 + k * 260, H)], fill=(15, 24, 21, 255), width=1)
    # foreground grass silhouette
    for x in range(0, W, 4):
        hgt = 40 + random.random() * 70
        d.line([(x, H), (x + random.uniform(-10, 10), H - hgt)], fill=(4, 7, 6, 255), width=2)
    return img


VILLAGE = village_layer()
FIELD = field_layer()


def sky(top, bottom, stars=True, moon=None):
    a = vgrad(top, bottom)
    if stars:
        r = np.random.default_rng(3)
        for _ in range(220):
            x, y = r.integers(0, W), r.integers(0, 380)
            a[y, x] = np.minimum(255, a[y, x] + r.integers(60, 170))
    img = Image.fromarray(a.astype(np.uint8))
    if moon:
        glow = Image.new("RGB", (W, H), (0, 0, 0))
        gd = ImageDraw.Draw(glow)
        mx, my, mr = moon
        gd.ellipse([mx - mr * 3, my - mr * 3, mx + mr * 3, my + mr * 3], fill=(40, 50, 55))
        glow = glow.filter(ImageFilter.GaussianBlur(40))
        img = Image.fromarray(np.minimum(255, np.asarray(img, int) + np.asarray(glow, int)).astype(np.uint8))
        d = ImageDraw.Draw(img)
        d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(200, 205, 190))
        d.ellipse([mx - mr + 10, my - mr - 4, mx + mr + 10, my + mr - 4], fill=tuple(int(c) for c in a[my, mx + mr]))
    return img


SKY_A = sky((6, 10, 22), (30, 40, 48), moon=(1020, 120, 34))
SKY_B = sky((3, 6, 12), (16, 26, 26), moon=None)


# ---------------------------------------------------------------- krasue head
def krasue_sprite(t, scale=1.0, reveal=1.0):
    """Floating head with long hair and a luminous ghost-light trail (stylized, no gore)."""
    s = 640
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    cx, cy = s // 2, 200
    # glow trail
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i in range(14):
        yy = cy + 70 + i * 22
        wob = 18 * math.sin(t * 3 + i * 0.7)
        r = 46 - i * 2.6
        col = (90, 255, 150, int(150 - i * 8)) if i % 3 else (255, 90, 90, int(120 - i * 7))
        gd.ellipse([cx + wob - r, yy - r * 0.7, cx + wob + r, yy + r * 0.7], fill=col)
    gd.ellipse([cx - 170, cy - 170, cx + 170, cy + 190], fill=(60, 255, 140, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(26))
    img.alpha_composite(glow)
    d = ImageDraw.Draw(img)
    # hair back
    d.ellipse([cx - 82, cy - 100, cx + 82, cy + 70], fill=(5, 5, 7, 255))
    # face
    d.ellipse([cx - 58, cy - 70, cx + 58, cy + 72], fill=(214, 220, 206, 255))
    # eyes: dark sockets + glowing pupils
    for ex in (-24, 24):
        d.ellipse([cx + ex - 15, cy - 14, cx + ex + 15, cy + 8], fill=(20, 26, 24, 255))
        p = 4 + 2 * math.sin(t * 6)
        d.ellipse([cx + ex - p, cy - 4 - p, cx + ex + p, cy - 4 + p], fill=(170, 255, 190, 255))
    # mouth: thin dark line
    d.line([(cx - 14, cy + 40), (cx + 14, cy + 42)], fill=(60, 30, 34, 255), width=3)
    # fringe
    d.chord([cx - 66, cy - 104, cx + 66, cy + 10], 180, 360, fill=(5, 5, 7, 255))
    # long hair strands falling at the sides, leaving the ghost-light trail visible
    for k in list(range(-9, -3)) + list(range(4, 10)):
        side = 1 if k > 0 else -1
        pts = []
        for j in range(18):
            yy = cy - 40 + j * 19
            sway = 12 * math.sin(t * 2.2 + j * 0.45 + k * 0.6) * (j / 17)
            xx = cx + side * (40 + (abs(k) - 4) * 7 + j * 2.2) + sway
            pts.append((xx, yy))
        d.line(pts, fill=(4, 4, 6, 230), width=6, joint="curve")
    if scale != 1.0:
        img = img.resize((int(s * scale), int(s * scale)), Image.LANCZOS)
    if reveal < 1.0:
        a = np.asarray(img).copy()
        a[..., 3] = (a[..., 3] * reveal).astype(np.uint8)
        img = Image.fromarray(a)
    return img


def ghost_light(img, x, y, r, intensity):
    """Add a soft green orb onto an RGB float array."""
    yy, xx = np.ogrid[:H, :W]
    d2 = ((xx - x) ** 2 + (yy - y) ** 2) / (r * r)
    g = np.exp(-d2)[..., None] * intensity
    core = np.exp(-d2 * 12)[..., None] * intensity
    img += g * np.array([40, 200, 110]) + core * np.array([200, 255, 210])
    return img


# ---------------------------------------------------------------- text
_fcache = {}


def font(sz):
    if sz not in _fcache:
        _fcache[sz] = ImageFont.truetype(FONT, sz, layout_engine=ImageFont.Layout.RAQM)
    return _fcache[sz]


def draw_text_center(img, text, y, sz, alpha, color=(235, 235, 225), stroke=4):
    if alpha <= 0:
        return img
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(sz)
    bb = d.textbbox((0, 0), text, font=f, stroke_width=stroke, language="th")
    tw = bb[2] - bb[0]
    if tw > W - 80:  # shrink to fit
        return draw_text_center(img, text, y, int(sz * (W - 80) / tw), alpha, color, stroke)
    x = (W - tw) // 2 - bb[0]
    d.text((x, y), text, font=f, fill=color + (int(255 * alpha),), stroke_width=stroke,
           stroke_fill=(0, 0, 0, int(220 * alpha)), language="th")
    out = img.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


# ---------------------------------------------------------------- frame
FIREFLIES = rng.random((40, 4))
VIGN = None


def vignette():
    yy, xx = np.ogrid[:H, :W]
    d = ((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2
    return np.clip(1.15 - 0.55 * d, 0.2, 1.0)[..., None]


VIGN = vignette()


def frame(i):
    t = i / FPS
    if t < 18.5:  # village establishing shots
        base = SKY_A.copy()
        base.paste(VILLAGE, (int(-20 + t * 1.2), 0), VILLAGE)
        a = np.asarray(base, float)
        a += fog(t, 0.22)
        for fx, fy, ph, sp in FIREFLIES:  # fireflies
            x = fx * W + 30 * math.sin(t * sp + ph * 6)
            y = 420 + fy * 250 + 15 * math.cos(t * sp * 1.3 + ph * 4)
            b = 0.5 + 0.5 * math.sin(t * 4 * sp + ph * 9)
            xi, yi = int(x), int(y)
            if 2 < xi < W - 3 and 2 < yi < H - 3:
                a[yi - 2:yi + 3, xi - 2:xi + 3] += np.array([120, 160, 60]) * b
        if t > 13:  # slow push toward the clothesline
            z = 1 + 0.25 * smooth(13, 18.5, t)
            im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
            cw, ch = int(W / z), int(H / z)
            x0, y0 = int(570 - cw / 2), int(420 - ch / 2)
            x0 = max(0, min(W - cw, x0)); y0 = max(0, min(H - ch, y0))
            a = np.asarray(im.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BICUBIC), float)
        bright = smooth(0, 3, t)
    elif t < 42:  # the field, green light approaching
        base = SKY_B.copy()
        base.paste(FIELD, (0, 0), FIELD)
        a = np.asarray(base, float)
        a += fog(t, 0.22, (120, 150, 140))
        p = smooth(24, 42, t)
        x = 900 - 420 * p + 40 * math.sin(t * 0.9)
        y = 385 + 90 * p + 10 * math.sin(t * 2.1)
        r = 10 + 70 * p ** 1.5
        flick = 0.85 + 0.15 * math.sin(t * 17) * math.sin(t * 5.3)
        inten = smooth(23.5, 26, t) * flick * (0.9 + 0.6 * p)
        a = ghost_light(a, x, y, r, inten)
        a *= 0.85 + 0.15 * smooth(19, 21, t)
        bright = 1.0
    elif t < 50.5:  # reveal
        base = SKY_B.copy()
        base.paste(FIELD, (0, 0), FIELD)
        a = np.asarray(base, float) * 0.55
        a += fog(t, 0.2, (110, 140, 130))
        a = ghost_light(a, W / 2, 330, 260, 0.35)
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")
        rev = smooth(42.6, 44.4, t)  # after 2s of dead silence
        sc = 1.05 + 0.35 * smooth(42.6, 50.5, t)
        if rev > 0:
            spr = krasue_sprite(t, sc, rev)
            jx = int(3 * math.sin(t * 40)) if 43 < t < 44 else 0
            im.alpha_composite(spr, (W // 2 - spr.width // 2 + jx, int(130 - 120 * sc) + int(8 * math.sin(t * 1.7))))
        a = np.asarray(im.convert("RGB"), float)
        if 42 <= t < 42.6:
            a *= 0.15  # blackout beat
        bright = 1.0
    else:  # morning after, damp sarong, final sting
        base = sky((70, 80, 90), (140, 145, 140), stars=False)
        b = np.asarray(base, float)
        im = Image.fromarray(b.astype(np.uint8))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 520, W, H], fill=(60, 64, 58))
        d.line([(0, 200), (W, 215)], fill=(30, 30, 30), width=4)
        # big sarong close-up with dark damp patches
        d.polygon([(470, 205), (810, 210), (795, 690), (485, 700)], fill=(110, 45, 55))
        for k in range(6):
            d.line([(470, 260 + k * 70), (808, 265 + k * 70)], fill=(140, 70, 70), width=6)
        damp = Image.new("L", (W, H), 0)
        dd = ImageDraw.Draw(damp)
        dd.ellipse([560, 330, 700, 470], fill=200)
        dd.ellipse([600, 440, 660, 640], fill=170)
        damp = damp.filter(ImageFilter.GaussianBlur(30))
        dark = Image.new("RGB", (W, H), (40, 12, 18))
        im = Image.composite(dark, im, damp)
        # drips
        for k, dx in enumerate((590, 625, 655)):
            yy = 700 + ((t * 120 + k * 70) % 30)
            d2 = ImageDraw.Draw(im)
            d2.ellipse([dx - 3, yy - 6, dx + 3, yy + 4], fill=(70, 30, 35))
        a = np.asarray(im, float)
        if t > 55.8:  # back to night for the last line, faint green glint behind the sarong
            nf = smooth(55.8, 56.8, t)
            a = a * (1 - 0.82 * nf)
            a = ghost_light(a, 930, 300, 30, 0.6 * nf * (0.6 + 0.4 * math.sin(t * 9)))
        bright = 1 - smooth(59.2, 60, t)
    # grade: grain, vignette, brightness
    a = a * VIGN
    a += rng.normal(0, 7, (H, W, 1))
    a *= bright
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    # letterbox bars
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 44], fill=(0, 0, 0))
    d.rectangle([0, H - 44, W, H], fill=(0, 0, 0))
    # text
    for s, e, txt in SUBS:
        al = env(t, s, e)
        if al > 0:
            if txt == "ผีกระสือ":
                img = draw_text_center(img, txt, 250, 130, al, (200, 235, 205), 6)
                img = draw_text_center(img, "ตำนานผีไทย", 410, 38, al * 0.85, (170, 180, 170), 3)
            elif s >= 56:
                img = draw_text_center(img, txt, 300, 56, al, (225, 240, 228), 5)
            else:
                img = draw_text_center(img, txt, H - 128, 40, al)
    al = env(t, CLOCK[0], CLOCK[1])
    if al > 0:
        img = draw_text_center(img, CLOCK[2], 90, 64, al * 0.9, (160, 230, 180), 3)
    return img


# ---------------------------------------------------------------- audio
def audio():
    n = SR * DUR
    ts = np.arange(n) / SR
    out = np.zeros(n)

    def envv(a, b, f=1.0):
        return np.clip((ts - a) / f, 0, 1) * np.clip((b - ts) / f, 0, 1)

    # low drone, swelling as light approaches; cut at 42s
    drone = (np.sin(2 * np.pi * 55 * ts) + 0.6 * np.sin(2 * np.pi * 55.7 * ts) + 0.4 * np.sin(2 * np.pi * 82.4 * ts))
    swell = 0.10 + 0.25 * np.clip((ts - 24) / 18, 0, 1)
    out += drone * swell * envv(0, 42, 2) * (ts < 42)
    # wind: filtered noise
    noise = rng.normal(0, 1, n)
    k = np.ones(400) / 400
    wind = np.convolve(noise, k, mode="same") * 6
    wind *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * ts)
    out += wind * 0.18 * envv(0, 42, 2) * (ts < 42)
    # crickets until 38s (they stop together)
    chirp = np.sin(2 * np.pi * 4300 * ts) * (np.sin(2 * np.pi * 30 * ts) > 0.3) * (np.sin(2 * np.pi * 1.6 * ts) > 0)
    chirp2 = np.sin(2 * np.pi * 4700 * ts) * (np.sin(2 * np.pi * 26 * ts) > 0.4) * (np.sin(2 * np.pi * 1.1 * ts + 1) > 0.2)
    out += (chirp + 0.7 * chirp2) * 0.035 * envv(0.5, 38.5, 0.25)
    # folk-ish plucked tones in the village section (pentatonic)
    notes = [220, 247, 294, 330, 392, 440]
    for j, st in enumerate(np.arange(2.0, 18.0, 1.35)):
        f = notes[(j * 3) % len(notes)]
        seg = (ts >= st) & (ts < st + 1.3)
        tt = ts[seg] - st
        out[seg] += 0.12 * np.sin(2 * np.pi * f * tt) * np.exp(-tt * 3.5) * (1 + 0.4 * np.sin(2 * np.pi * f * 2 * tt))
    # heartbeat 30-42
    for st in np.arange(30, 42, 0.9 - 0.25 * 0):
        for off, amp in ((0, 1.0), (0.18, 0.7)):
            seg = (ts >= st + off) & (ts < st + off + 0.15)
            tt = ts[seg] - st - off
            out[seg] += 0.35 * amp * np.sin(2 * np.pi * 48 * tt) * np.exp(-tt * 30) * np.clip((st - 29) / 8, 0.2, 1)
    # 42-42.6 silence; 42.6 sting: dissonant cluster + noise burst
    seg = (ts >= 42.6) & (ts < 47)
    tt = ts[seg] - 42.6
    clus = sum(np.sin(2 * np.pi * f * tt) for f in (233, 247, 262, 466, 494))
    out[seg] += 0.22 * clus * np.exp(-tt * 0.9)
    out[seg] += 0.3 * rng.normal(0, 1, seg.sum()) * np.exp(-tt * 6)
    # eerie high whine during reveal
    seg = (ts >= 43) & (ts < 50.5)
    tt = ts[seg] - 43
    out[seg] += 0.05 * np.sin(2 * np.pi * (1200 + 40 * np.sin(2 * np.pi * 0.5 * tt)) * tt) * np.clip(tt / 2, 0, 1)
    # morning: birds, water drips
    for st in np.arange(51, 55.5, 0.7):
        seg = (ts >= st) & (ts < st + 0.12)
        tt = ts[seg] - st
        out[seg] += 0.06 * np.sin(2 * np.pi * (2500 + 6000 * tt) * tt)
    for st in np.arange(51.2, 56, 0.55):
        seg = (ts >= st) & (ts < st + 0.05)
        tt = ts[seg] - st
        out[seg] += 0.18 * np.sin(2 * np.pi * 900 * (1 - tt * 6) * tt) * np.exp(-tt * 80)
    # final: low drone returns + single bell
    seg = ts >= 56
    tt = ts[seg] - 56
    out[seg] += 0.15 * np.sin(2 * np.pi * 49 * tt) * np.clip(tt, 0, 1) * np.clip((4 - tt) / 0.6, 0, 1)
    seg = (ts >= 58.2)
    tt = ts[seg] - 58.2
    out[seg] += 0.25 * (np.sin(2 * np.pi * 880 * tt) + 0.5 * np.sin(2 * np.pi * 1320 * tt)) * np.exp(-tt * 2.2)
    out *= 0.9 / max(1e-6, np.abs(out).max())
    stereo = np.stack([out, np.roll(out, 300)], axis=1)
    with wave.open("krasue_audio.wav", "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((stereo * 32767).astype(np.int16).tobytes())


def main():
    audio()
    p = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", "krasue_audio.wav", "-c:v", "libx264", "-preset", "medium",
         "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest",
         "-movflags", "+faststart", OUT],
        stdin=subprocess.PIPE)
    for i in range(N):
        p.stdin.write(frame(i).tobytes())
        if i % 240 == 0:
            print(f"frame {i}/{N}", flush=True)
    p.stdin.close()
    p.wait()
    print("done", OUT)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "preview":
        for sec in (4, 15, 28, 40, 46, 53, 58):
            frame(sec * FPS).save(f"preview_{sec:02d}.png")
    else:
        main()
