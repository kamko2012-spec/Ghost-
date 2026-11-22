"""Krasue (ผีกระสือ) ~60s horror clip in stickman style, with Thai voiceover.

Needs: edge-tts (pip), ffmpeg, Loma Thai font. Network access to speech.platform.bing.com for TTS.
Usage: python3 render_stickman.py [out.mp4] [preview]
"""
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SR = 1280, 720, 24, 44100
SS = 2  # supersampling for smooth lines
FONT = "/usr/share/fonts/opentype/tlwg/Loma-Bold.otf"
OUT = sys.argv[1] if len(sys.argv) > 1 else "krasue_stickman.mp4"
PREVIEW = len(sys.argv) > 2 and sys.argv[2] == "preview"
VOICE, RATE = "th-TH-NiwatNeural", "-18%"
TTS_DIR = f"tts_cache{RATE}"
rng = np.random.default_rng(11)

LINES = [
    "ผีกระสือ... ตำนานผีที่คนอีสานเล่าต่อกันมา",
    "ที่หมู่บ้านเล็กๆ ริมทุ่งนา มีเด็กชายชื่อต้น มาอยู่กับยาย",
    "ยายเตือนต้นไว้ข้อเดียว... อย่าตากผ้าทิ้งไว้นอกบ้านตอนกลางคืน",
    "แต่คืนนั้น ต้นลืมเก็บผ้าถุงของยาย",
    "ตีสองสิบเจ็ดนาที ต้นตื่นขึ้นมากลางดึก",
    "เขาเห็นแสงสีเขียว ลอยต่ำๆ อยู่เหนือทุ่งนา",
    "แสงนั้น... ลอยใกล้เข้ามา ช้าๆ",
    "แล้วเสียงจิ้งหรีด ก็เงียบลงพร้อมกัน ทั้งทุ่ง",
    "มันคือหัวผู้หญิง... ที่ไม่มีร่างกาย",
    "มันลอยไปที่ราวผ้า แล้วเอาผ้าถุงของยาย... เช็ดปาก",
    "เช้าวันต่อมา ผ้าถุงบนราวเปียกชุ่ม ทั้งที่ฝนไม่ได้ตก",
    "คืนนี้... คุณเก็บผ้าเข้าบ้านแล้วหรือยัง",
]
GAP_BEFORE = {1: 1.6, 2: 1.2, 3: 1.6, 4: 1.6, 5: 1.4, 6: 1.6, 7: 1.4, 8: 3.0, 9: 1.4, 10: 1.8, 11: 1.8}


# ---------------------------------------------------------------- voiceover
def tts():
    os.makedirs(TTS_DIR, exist_ok=True)
    clips = []
    for i, line in enumerate(LINES):
        mp3 = f"{TTS_DIR}/l{i:02d}.mp3"
        wav = f"{TTS_DIR}/l{i:02d}.wav"
        if not os.path.exists(mp3) or os.path.getsize(mp3) == 0:
            cmd = ["edge-tts", "--voice", VOICE, f"--rate={RATE}", "--text", line, "--write-media", mp3]
            if os.environ.get("HTTPS_PROXY"):
                cmd += ["--proxy", os.environ["HTTPS_PROXY"]]
            subprocess.run(cmd, check=True, capture_output=True)
        # deeper, slightly echoey storyteller voice
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-af",
                        "asetrate=24000*0.92,aresample=44100,atempo=1.087,aecho=0.8:0.5:70:0.12,"
                        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                        "silenceremove=start_periods=1:start_threshold=-45dB,areverse",
                        "-ac", "1", "-ar", str(SR), wav], check=True)
        with wave.open(wav) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
        clips.append(a)
    return clips


CLIPS = tts()
T = []
cur = 0.9
for i, c in enumerate(CLIPS):
    cur += GAP_BEFORE.get(i, 0)
    T.append((cur, cur + len(c) / SR))
    cur = T[-1][1]
DUR = max(60, math.ceil(cur + 2.2))
N = FPS * DUR
S = lambda i: T[i][0]  # noqa: E731
E = lambda i: T[i][1]  # noqa: E731
BLACK = (E(7) + 0.4, S(8))  # dead-silence blackout before the reveal


# ---------------------------------------------------------------- helpers
def smooth(a, b, t):
    if t <= a:
        return 0.0
    if t >= b:
        return 1.0
    x = (t - a) / (b - a)
    return x * x * (3 - 2 * x)


def env(t, a, b, f=0.3):
    return smooth(a - f, a, t) * (1 - smooth(b, b + f, t))


def jit(t, k, amp=1.6):
    """Hand-drawn 'boiling line' jitter, re-rolled 8 times per second."""
    f = int(t * 8)
    v = math.sin(f * 12.9898 + k * 78.233) * 43758.5453
    return (v - math.floor(v) - 0.5) * 2 * amp


CHALK = (236, 234, 222)
INK = (34, 32, 36)
GREEN = (120, 255, 160)
RED = (220, 60, 60)


class Pen:
    def __init__(self, img, t, col=CHALK, w=5, shake=1.0):
        self.d = ImageDraw.Draw(img)
        self.t, self.col, self.w, self.shake, self.k = t, col, w, shake, 0

    def p(self, x, y):
        self.k += 1
        return (SS * (x + jit(self.t, self.k, 1.4 * self.shake)), SS * (y + jit(self.t, self.k + 500, 1.4 * self.shake)))

    def line(self, pts, col=None, w=None):
        pts = [self.p(*q) for q in pts]
        ww = SS * (w or self.w)
        self.d.line(pts, fill=col or self.col, width=ww, joint="curve")
        for q in (pts[0], pts[-1]):
            self.d.ellipse([q[0] - ww / 2, q[1] - ww / 2, q[0] + ww / 2, q[1] + ww / 2], fill=col or self.col)

    def circle(self, x, y, r, col=None, fill=None, w=None):
        cx, cy = self.p(x, y)
        self.d.ellipse([cx - SS * r, cy - SS * r, cx + SS * r, cy + SS * r], outline=col or self.col,
                       fill=fill, width=SS * (w or self.w))

    def dot(self, x, y, r, col=None):
        cx, cy = self.p(x, y)
        self.d.ellipse([cx - SS * r, cy - SS * r, cx + SS * r, cy + SS * r], fill=col or self.col)

    def poly(self, pts, fill, outline=None):
        self.d.polygon([self.p(*q) for q in pts], fill=fill, outline=outline)


def pol(x, y, ang, ln):
    a = math.radians(ang)
    return x + ln * math.cos(a), y + ln * math.sin(a)


def stickman(pen, x, y, s, arms=((120, 100), (60, 80)), legs=(105, 75), tilt=0, kind="kid", look=1):
    """x,y = feet on ground. Angles in degrees, 90 = straight down."""
    hip = (x, y - 0.75 * s)
    neck = pol(*hip, -90 + tilt, 0.62 * s)
    head = pol(*neck, -90 + tilt, 0.24 * s)
    for la in legs:
        knee = pol(*hip, la, 0.38 * s)
        pen.line([hip, knee, pol(*knee, la, 0.38 * s)])
    pen.line([hip, neck])
    sh = pol(*hip, -90 + tilt, 0.5 * s)
    for ua, la in arms:
        el = pol(*sh, ua, 0.3 * s)
        pen.line([sh, el, pol(*el, la, 0.3 * s)])
    pen.circle(*head, 0.2 * s, fill=None)
    hx, hy = head
    pen.dot(hx + look * 0.08 * s, hy - 0.02 * s, 0.03 * s + 1)
    if kind == "kid":  # red cap = Ton's signature item
        pen.line([(hx - 0.2 * s, hy - 0.07 * s), (hx, hy - 0.2 * s), (hx + 0.2 * s, hy - 0.07 * s)], col=RED, w=6)
        pen.line([(hx + look * 0.15 * s, hy - 0.08 * s), (hx + look * 0.34 * s, hy - 0.06 * s)], col=RED, w=6)
    elif kind == "grandma":
        pen.circle(hx - look * 0.17 * s, hy - 0.16 * s, 0.08 * s, fill=None)  # hair bun
    return head


def krasue(pen, x, y, s, t, wipe=0.0):
    """Floating head with long hair; glowing strands hang below (stylized, no gore)."""
    for k in range(5):  # dangling glow strands
        pts = [(x + (k - 2) * 0.09 * s + 0.06 * s * math.sin(t * 3 + j * 0.8 + k), y + 0.2 * s + j * 0.11 * s)
               for j in range(8)]
        pen.line(pts, col=(GREEN if k % 2 else (230, 110, 110)), w=4)
    for k in range(-6, 7):  # hair
        if abs(k) < 3:
            continue
        side = 1 if k > 0 else -1
        pts = [(x + side * (0.12 * s + abs(k) * 0.018 * s + j * 0.012 * s) + 0.03 * s * math.sin(t * 2 + j * 0.6 + k),
                y - 0.15 * s + j * 0.09 * s) for j in range(10)]
        pen.line(pts, w=4)
    pen.circle(x, y, 0.22 * s, fill=(18, 20, 26))
    pen.line([(x - 0.2 * s, y - 0.08 * s), (x, y - 0.21 * s), (x + 0.2 * s, y - 0.08 * s)], w=6)  # fringe
    blink = 0.2 if (t % 3.3) < 0.12 else 1
    for ex in (-0.08, 0.08):
        pen.dot(x + ex * s, y, 0.035 * s * blink + 1, col=GREEN)
    m = 0.05 * s * (1 + wipe)
    pen.line([(x - m, y + 0.11 * s), (x + m, y + 0.12 * s)], col=(200, 90, 90), w=4)


def orb(a, x, y, r, inten, col=(40, 200, 110)):
    x0, x1 = max(0, int(x - 3 * r)), min(W, int(x + 3 * r))
    y0, y1 = max(0, int(y - 3 * r)), min(H, int(y + 3 * r))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.ogrid[y0:y1, x0:x1]
    d2 = ((xx - x) ** 2 + (yy - y) ** 2) / (r * r)
    a[y0:y1, x0:x1] += (np.exp(-d2)[..., None] * np.array(col) + np.exp(-d2 * 14)[..., None] * 220) * inten


def bg(top, bottom):
    y = np.linspace(0, 1, H * SS)[:, None, None]
    g = np.array(top, float) * (1 - y) + np.array(bottom, float) * y
    return Image.fromarray(np.broadcast_to(g, (H * SS, W * SS, 3)).astype(np.uint8))


BG_NIGHT = bg((8, 12, 28), (22, 30, 44))
BG_DUSK = bg((40, 28, 60), (110, 70, 70))
BG_DAY = bg((214, 224, 230), (240, 236, 222))
BG_BLACK = bg((4, 5, 8), (10, 12, 16))
STARS = [(rng.integers(0, W), rng.integers(50, 380), rng.random()) for _ in range(90)]


def stars(pen, t):
    for i, (x, y, p) in enumerate(STARS):
        if math.sin(t * 2 + p * 20) > -0.6:
            pen.dot(x, y, 1.3)


def house(pen, x, base, w, h, window_lit=False):
    pen.line([(x, base - 0.5 * h), (x + w, base - 0.5 * h), (x + w, base - 0.18 * h), (x, base - 0.18 * h), (x, base - 0.5 * h)])
    pen.line([(x - 0.12 * w, base - 0.5 * h), (x + w / 2, base - h), (x + 1.12 * w, base - 0.5 * h)])
    for px in np.linspace(x + 8, x + w - 8, 4):
        pen.line([(px, base - 0.18 * h), (px, base)])
    wx = x + 0.6 * w
    if window_lit:
        pen.poly([(wx, base - 0.44 * h), (wx + 30, base - 0.44 * h), (wx + 30, base - 0.26 * h), (wx, base - 0.26 * h)],
                 fill=(200, 160, 70))
    pen.line([(wx, base - 0.44 * h), (wx + 30, base - 0.44 * h), (wx + 30, base - 0.26 * h), (wx, base - 0.26 * h), (wx, base - 0.44 * h)], w=3)
    # stairs
    pen.line([(x - 30, base), (x + 10, base - 0.18 * h)], w=3)


def clothesline(pen, x0, x1, top, base, t, wet=0.0, swing=0.0, sarong_col=(150, 60, 70)):
    pen.line([(x0, base), (x0, top)])
    pen.line([(x1, base), (x1, top)])
    pen.line([(x0, top + 4), (x1, top + 8)], w=3)
    cx = (x0 + x1) / 2
    sw = 8 * math.sin(t * 1.3) + swing
    pts = [(cx - 50, top + 6), (cx + 50, top + 8), (cx + 48 + sw, top + 150), (cx - 48 + sw, top + 152)]
    pen.poly(pts, fill=sarong_col)
    for k in range(1, 4):
        yy = top + 8 + k * 36
        pen.line([(cx - 49 + sw * k / 4, yy), (cx + 49 + sw * k / 4, yy + 2)], col=(200, 120, 110), w=3)
    if wet > 0:
        pen.poly([(cx - 22 + sw * .5, top + 40), (cx + 25 + sw * .5, top + 45), (cx + 18 + sw, top + 150), (cx - 15 + sw, top + 150)],
                 fill=tuple(int(c * (1 - 0.5 * wet)) for c in sarong_col))
    return cx + sw, top + 150


# ---------------------------------------------------------------- text
_f = {}


def font(sz):
    if sz not in _f:
        _f[sz] = ImageFont.truetype(FONT, sz, layout_engine=ImageFont.Layout.RAQM)
    return _f[sz]


def text(img, s, y, sz, alpha, col=(240, 240, 230), stroke=4):
    if alpha <= 0.01:
        return img
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    bb = d.textbbox((0, 0), s, font=font(sz), stroke_width=stroke, language="th")
    if bb[2] - bb[0] > W - 80:
        return text(img, s, y, int(sz * (W - 80) / (bb[2] - bb[0])), alpha, col, stroke)
    d.text(((W - (bb[2] - bb[0])) // 2 - bb[0], y), s, font=font(sz), fill=col + (int(255 * alpha),),
           stroke_width=stroke, stroke_fill=(0, 0, 0, int(230 * alpha)), language="th")
    out = img.convert("RGBA")
    out.alpha_composite(lay)
    return out.convert("RGB")


# ---------------------------------------------------------------- scenes
GROUND = 560


def frame(i):
    t = i / FPS
    orbs = []
    shake = 1.0
    if t < S(1) - 0.3:  # A: title + village
        img = BG_NIGHT.copy(); pen = Pen(img, t)
        stars(pen, t)
        pen.circle(1060, 120, 34, fill=(220, 220, 200))
        pen.line([(0, GROUND), (W, GROUND)])
        house(pen, 160, GROUND, 220, 260, True)
        clothesline(pen, 820, 1060, 380, GROUND, t)
        for k in range(14):
            orbs.append((80 + k * 90 + 30 * math.sin(t + k), 600 + 40 * math.sin(t * 0.7 + k * 2), 6,
                         0.5 + 0.5 * math.sin(t * 3 + k), (150, 170, 40)))
    elif t < S(3) - 0.3:  # B: grandma warns Ton
        img = BG_DUSK.copy(); pen = Pen(img, t)
        pen.line([(0, GROUND), (W, GROUND)])
        house(pen, 40, GROUND, 200, 240)
        clothesline(pen, 960, 1200, 380, GROUND, t)
        wag = 25 * math.sin(t * 7) if t > S(2) else 0
        point = t > S(2) + 1.6
        g_arms = ((-10, -10), (110, 90)) if point else ((-40, -70 + wag), (110, 90))
        stickman(pen, 470, GROUND, 230, arms=g_arms, legs=(100, 82), tilt=12, kind="grandma")
        pen.line([(560, GROUND), (548, GROUND - 120)], w=4)  # cane
        if point:
            pen.line([(1040, 340), (1060, 360), (1080, 340)], col=(255, 230, 120), w=4)  # arrow hint at sarong
        stickman(pen, 720, GROUND, 160, arms=((110, 95), (70, 85)), legs=(100, 80), kind="kid", look=-1)
    elif t < S(4) - 0.2:  # C: Ton asleep, sarong left outside
        img = BG_NIGHT.copy(); pen = Pen(img, t)
        stars(pen, t)
        pen.line([(0, GROUND), (W, GROUND)])
        # big house cross-section
        pen.line([(100, 250), (620, 250), (620, 470), (100, 470), (100, 250)])
        pen.line([(60, 250), (360, 110), (660, 250)])
        for px in (120, 300, 480, 600):
            pen.line([(px, 470), (px, GROUND)])
        pen.line([(160, 440), (420, 440)], w=3)  # mat
        pen.circle(190, 418, 18)
        pen.line([(208, 425), (360, 428)])
        pen.line([(360, 428), (400, 438)])
        pen.line([(250, 427), (300, 412)])
        pen.line([(172, 402), (190, 398), (208, 404)], col=RED, w=6)
        for k in range(3):
            ph = (t * 0.6 + k / 3) % 1
            pen.d.text((SS * (230 + ph * 60 + k * 10), SS * (390 - ph * 120)), "z", fill=CHALK, font=font(SS * (20 + 10 * k)))
        clothesline(pen, 860, 1100, 380, GROUND, t)
        pen.circle(1080, 110, 30, fill=(220, 220, 200))
    elif t < S(5) - 0.2:  # D: 02:17, Ton wakes and gets up
        img = BG_BLACK.copy(); pen = Pen(img, t)
        p = smooth(S(4) + 1.0, E(4) + 0.3, t)
        pen.line([(0, 520), (W, 520)], w=3)
        if p < 0.5:  # sitting up
            stickman(pen, 620, 520, 150, arms=((80, 90), (100, 90)), legs=(0, 5), tilt=-5 + 40 * (0.5 - p), kind="kid")
        else:
            x = 620 + (p - 0.5) * 500
            st = 25 * math.sin(t * 8)
            stickman(pen, x, 520, 150, arms=((90 + st, 95), (90 - st, 85)), legs=(90 + st, 90 - st), kind="kid")
    elif t < BLACK[0]:  # E: at the window, green light approaching
        img = BG_BLACK.copy(); pen = Pen(img, t)
        shake = 1 + 2.5 * smooth(S(7), S(7) + 1.2, t)
        pen.shake = shake
        wx0, wy0, wx1, wy1 = 560, 120, 1200, 520
        pen.poly([(wx0, wy0), (wx1, wy0), (wx1, wy1), (wx0, wy1)], fill=(12, 20, 32))
        for k, (x, y, ph) in enumerate(STARS[:40]):
            sx, sy = wx0 + (x % (wx1 - wx0)), wy0 + 10 + (y % 160)
            pen.dot(sx, sy, 1.2)
        hz = 340
        pen.line([(wx0, hz), (wx1, hz)], w=3)
        for k in range(1, 5):
            yy = hz + (wy1 - hz) * (k / 5) ** 1.5
            pen.line([(wx0, yy), (wx1, yy)], col=(70, 90, 80), w=2)
        pen.line([(wx0, wy0), (wx1, wy0), (wx1, wy1), (wx0, wy1), (wx0, wy0)], w=7)
        pen.line([((wx0 + wx1) / 2, wy0), ((wx0 + wx1) / 2, wy1)], w=5)
        p = smooth(S(5), BLACK[0], t)
        lx = 1100 - 380 * p + 30 * math.sin(t * 0.9)
        ly = hz - 6 + 110 * p + 8 * math.sin(t * 2.2)
        fl = 0.85 + 0.15 * math.sin(t * 17) * math.sin(t * 5.3)
        orbs.append((lx, ly, 6 + 45 * p ** 1.6, smooth(S(5) - 0.2, S(5) + 0.8, t) * fl * (0.8 + 0.7 * p), (40, 200, 110)))
        stickman(pen, 380, 560, 210, arms=((60, 20), (120, 160)), legs=(100, 80), kind="kid", look=1)
        if t > S(7) + 0.8:
            pen.line([(440, 330), (446, 300)], w=3); pen.line([(460, 340), (470, 315)], w=3)  # fear marks
    elif t < S(9) - 0.2:  # F: blackout then reveal
        img = BG_BLACK.copy(); pen = Pen(img, t)
        if t >= BLACK[1]:
            u = t - BLACK[1]
            sc = 520 + 120 * smooth(0, E(8) - BLACK[1] + 0.5, u)
            jx = 6 * math.sin(t * 50) if u < 0.6 else 0
            krasue(pen, W / 2 + jx, 215 + 8 * math.sin(t * 1.7), sc, t)
            orbs.append((W / 2, 270, 220, 0.25, (40, 200, 110)))
    elif t < S(10) - 0.3:  # G: krasue wipes its mouth on grandma's sarong
        img = BG_NIGHT.copy(); pen = Pen(img, t)
        stars(pen, t)
        pen.line([(0, GROUND), (W, GROUND)])
        house(pen, 40, GROUND, 260, 300)
        pen.circle(40 + 0.6 * 260 + 15, GROUND - 0.36 * 300, 11)  # Ton peeking from window
        pen.dot(40 + 0.6 * 260 + 19, GROUND - 0.37 * 300, 2.5)
        u = smooth(S(9) - 0.2, S(9) + 1.6, t)
        wipe = math.sin(t * 9) if t > S(9) + 2.2 else 0
        sx, sy = clothesline(pen, 640, 960, 330, GROUND, t, swing=-14 * abs(wipe) if wipe else 0)
        kx = 1200 - 400 * u + 22 * wipe
        ky = 300 + 16 * math.sin(t * 1.5)
        krasue(pen, kx, ky, 200, t, wipe=abs(wipe))
        orbs.append((kx, ky + 20, 90, 0.35, (40, 200, 110)))
    elif t < S(11) - 0.4:  # H: morning, the sarong is soaked
        img = BG_DAY.copy(); pen = Pen(img, t, col=INK)
        pen.line([(0, GROUND), (W, GROUND)])
        pen.circle(150, 120, 40, col=(230, 180, 60), fill=(250, 220, 120))
        sx, sy = clothesline(pen, 520, 840, 300, GROUND, t, wet=1.0)
        for k in range(3):
            ph = (t * 1.4 + k / 3) % 1
            pen.dot(sx - 15 + k * 15, sy + 10 + ph * (GROUND - sy - 10), 4, col=(120, 40, 50))
        stickman(pen, 300, GROUND, 220, arms=((70, 100), (110, 80)), legs=(100, 82), tilt=12, kind="grandma")
        pen.line([(370, GROUND), (360, GROUND - 120)], w=4)
        stickman(pen, 1020, GROUND, 160, arms=((-150, -120), (-30, -60)), legs=(105, 75), kind="kid", look=-1)
        pen.d.text((SS * 1070, SS * 250), "!", fill=RED, font=font(SS * 60))
    else:  # I: final line, eyes in the dark
        img = BG_BLACK.copy(); pen = Pen(img, t)
        bl = (t % 2.7) < 0.15
        if not bl and t > S(11) + 1.0:
            for ex in (1040, 1075):
                pen.dot(ex, 160, 6, col=GREEN)
            orbs.append((1057, 160, 40, 0.25 * smooth(S(11) + 1, S(11) + 2, t), (40, 200, 110)))
    img = img.resize((W, H), Image.LANCZOS)
    a = np.asarray(img, float).copy()
    for o in orbs:
        orb(a, *o)
    a += rng.normal(0, 3, (H, W, 1))
    fade = smooth(0, 0.8, t) * (1 - smooth(DUR - 0.8, DUR, t))
    if BLACK[0] <= t < BLACK[1]:
        fade = 0
    img = Image.fromarray(np.clip(a * fade, 0, 255).astype(np.uint8))
    # subtitles
    if t < S(1):
        img = text(img, "ผีกระสือ", 220, 140, env(t, 0.6, S(1) - 0.6, 0.5), (190, 255, 205), 7)
    for k, line in enumerate(LINES):
        al = env(t, S(k), E(k) + 0.25, 0.2)
        if al <= 0:
            continue
        if k == 11:
            img = text(img, line, 300, 60, al, (220, 245, 228), 5)
        else:
            img = text(img, line, H - 110, 40, al)
    if S(4) - 0.2 <= t < S(5) - 0.2:
        img = text(img, "02:17", 40, 80, env(t, S(4), S(5) - 0.6, 0.4), (150, 240, 170), 4)
    return img


# ---------------------------------------------------------------- audio
def audio():
    n = SR * DUR
    ts = np.arange(n) / SR
    amb = np.zeros(n)

    def win(a, b, f=0.8):
        return np.clip((ts - a) / f, 0, 1) * np.clip((b - ts) / f, 0, 1)

    # crickets: stop together during line 7
    c1 = np.sin(2 * np.pi * 4300 * ts) * (np.sin(2 * np.pi * 30 * ts) > 0.3) * (np.sin(2 * np.pi * 1.6 * ts) > 0)
    c2 = np.sin(2 * np.pi * 4700 * ts) * (np.sin(2 * np.pi * 26 * ts) > 0.4) * (np.sin(2 * np.pi * 1.1 * ts + 1) > 0.2)
    amb += (c1 + 0.7 * c2) * 0.03 * win(0.3, S(7) + 1.3, 0.15) * ((ts < S(1) - 0.3) | (ts > S(3) - 0.3))
    # wind
    wnd = np.convolve(rng.normal(0, 1, n), np.ones(400) / 400, mode="same") * 6
    amb += wnd * 0.12 * win(0, BLACK[0], 1.5)
    # plucked pentatonic tune for the village/grandma part
    notes = [220, 262, 294, 330, 392, 440]
    for j, st in enumerate(np.arange(1.0, S(3) - 0.5, 1.2)):
        f = notes[(j * 2 + j // 3) % len(notes)]
        seg = (ts >= st) & (ts < st + 1.2)
        tt = ts[seg] - st
        amb[seg] += 0.09 * np.sin(2 * np.pi * f * tt) * np.exp(-tt * 3.5)
    # drone swelling from 02:17 until the blackout
    dr = np.sin(2 * np.pi * 55 * ts) + 0.6 * np.sin(2 * np.pi * 55.7 * ts) + 0.4 * np.sin(2 * np.pi * 82.4 * ts)
    amb += dr * (0.06 + 0.2 * np.clip((ts - S(5)) / (BLACK[0] - S(5)), 0, 1)) * win(S(4) - 0.5, BLACK[0], 1.0) * (ts < BLACK[0])
    # heartbeat
    for st in np.arange(S(6), BLACK[0] - 0.2, 0.85):
        for off, amp in ((0, 1.0), (0.18, 0.7)):
            seg = (ts >= st + off) & (ts < st + off + 0.15)
            tt = ts[seg] - st - off
            amb[seg] += 0.32 * amp * np.sin(2 * np.pi * 48 * tt) * np.exp(-tt * 30)
    # sting at the reveal
    seg = (ts >= BLACK[1]) & (ts < BLACK[1] + 4)
    tt = ts[seg] - BLACK[1]
    amb[seg] += 0.17 * sum(np.sin(2 * np.pi * f * tt) for f in (233, 247, 262, 466, 494)) * np.exp(-tt * 1.0)
    amb[seg] += 0.3 * rng.normal(0, 1, seg.sum()) * np.exp(-tt * 7)
    # eerie whine while the head is on screen
    seg = (ts >= BLACK[1] + 0.5) & (ts < S(10) - 0.3)
    tt = ts[seg] - BLACK[1]
    amb[seg] += 0.035 * np.sin(2 * np.pi * (1200 + 40 * np.sin(np.pi * tt)) * tt)
    # morning birds + drips
    for st in np.arange(S(10), S(11) - 0.6, 0.8):
        seg = (ts >= st) & (ts < st + 0.12)
        tt = ts[seg] - st
        amb[seg] += 0.05 * np.sin(2 * np.pi * (2500 + 6000 * tt) * tt)
    for st in np.arange(S(10) + 0.2, S(11) - 0.5, 0.5):
        seg = (ts >= st) & (ts < st + 0.05)
        tt = ts[seg] - st
        amb[seg] += 0.15 * np.sin(2 * np.pi * 900 * (1 - tt * 6) * tt) * np.exp(-tt * 80)
    # ending drone + single bell
    seg = ts >= S(11)
    tt = ts[seg] - S(11)
    amb[seg] += 0.12 * np.sin(2 * np.pi * 49 * tt) * np.clip(tt, 0, 1) * np.clip((DUR - S(11) - tt) / 0.8, 0, 1)
    seg = ts >= E(11) + 0.3
    tt = ts[seg] - E(11) - 0.3
    amb[seg] += 0.22 * (np.sin(2 * np.pi * 880 * tt) + 0.5 * np.sin(2 * np.pi * 1320 * tt)) * np.exp(-tt * 2.2)
    amb *= 0.4 / max(1e-6, np.abs(amb).max())
    # voiceover on top
    vo = np.zeros(n)
    for (s, _), c in zip(T, CLIPS):
        a = int(s * SR)
        vo[a:a + len(c)] += c[: n - a]
    vo *= 0.85 / max(1e-6, np.abs(vo).max())
    duck = 1 - 0.45 * np.convolve((np.abs(vo) > 0.02).astype(float), np.ones(4410) / 4410, mode="same")
    mix = vo + amb * duck
    mix *= 0.95 / np.abs(mix).max()
    st = np.stack([mix, mix], 1)
    st[:, 1] = 0.85 * mix + 0.15 * np.roll(amb * duck, 400)
    with wave.open("stick_audio.wav", "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(st, -1, 1) * 32767).astype(np.int16).tobytes())


def main():
    print(f"duration {DUR}s, lines:", [(round(a, 1), round(b, 1)) for a, b in T], flush=True)
    if PREVIEW:
        for k, tt in enumerate([1.5, S(2) + 2, S(3) + 1, S(4) + 2, S(6), S(8) + 1, S(9) + 3, S(10) + 1, S(11) + 1.5]):
            frame(int(tt * FPS)).save(f"sp_{k}.png")
        return
    audio()
    p = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-i", "stick_audio.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
    for i in range(N):
        p.stdin.write(frame(i).tobytes())
        if i % 240 == 0:
            print(f"frame {i}/{N}", flush=True)
    p.stdin.close(); p.wait()
    os.remove("stick_audio.wav")
    print("done", OUT)


if __name__ == "__main__":
    main()
