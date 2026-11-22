"""Krasue (ผีกระสือ) 60s horror clip, stickman style, Thai voiceover with per-line emotion.

Needs: edge-tts (pip), ffmpeg, Loma Thai font, network access to speech.platform.bing.com.
Usage: python3 render_stickman.py [out.mp4] [preview]
"""
import hashlib
import math
import os
import subprocess
import sys
import time
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SR = 1280, 720, 24, 44100
SS = 2  # draw at 2x: smooth lines + room for camera zoom
FONT = "/usr/share/fonts/opentype/tlwg/Loma-Bold.otf"
OUT = sys.argv[1] if len(sys.argv) > 1 else "krasue_stickman.mp4"
PREVIEW = len(sys.argv) > 2 and sys.argv[2] == "preview"
TTS_DIR = "tts_cache"
rng = np.random.default_rng(11)

NARR, GRAN = "th-TH-NiwatNeural", "th-TH-PremwadeeNeural"
# key, voice, rate, pitch, volume, style, gap before, text
SCRIPT = [
    ("title", NARR, "-15%", "-4Hz", "+0%", "calm", 0.0, "ผีกระสือ... ตำนานผีที่คนอีสานเล่าต่อกันมา"),
    ("intro", NARR, "-12%", "+0Hz", "+0%", "calm", 1.4, "ที่หมู่บ้านเล็กๆ ริมทุ่งนา มีเด็กชายชื่อต้น มาอยู่กับยาย"),
    ("warn", NARR, "-15%", "-3Hz", "+0%", "calm", 1.0, "ยายเตือนต้นไว้ข้อเดียว..."),
    ("rule", GRAN, "-22%", "-18Hz", "+0%", "granny", 0.5, "อย่าตากผ้าทิ้งไว้นอกบ้านตอนกลางคืนนะลูก"),
    ("forgot", NARR, "-15%", "-5Hz", "+0%", "calm", 1.4, "แต่คืนนั้น... ต้นลืมเก็บผ้าถุงของยาย"),
    ("clock", NARR, "-18%", "-6Hz", "-5%", "tense", 1.6, "ตีสองสิบเจ็ดนาที ต้นสะดุ้งตื่นขึ้นมากลางดึก"),
    ("light", NARR, "-18%", "-6Hz", "-5%", "tense", 1.3, "เขาเห็นแสงสีเขียว ลอยต่ำๆ อยู่เหนือทุ่งนา"),
    ("closer", NARR, "-28%", "-8Hz", "-10%", "tense", 1.4, "แสงนั้น... ลอยใกล้เข้ามา... ช้าๆ"),
    ("silent", NARR, "-28%", "-10Hz", "-20%", "whisper", 1.3, "แล้วเสียงจิ้งหรีด... ก็เงียบลงพร้อมกัน ทั้งทุ่ง"),
    ("reveal", NARR, "-30%", "-12Hz", "-10%", "dread", 3.0, "มันคือหัวผู้หญิง... ที่ไม่มีร่างกาย"),
    ("wipe", NARR, "-25%", "-10Hz", "-5%", "dread", 1.2, "มันลอยไปที่ราวผ้า แล้วเอาผ้าถุงของยาย... เช็ดปาก"),
    ("morning", NARR, "-15%", "-6Hz", "+0%", "calm", 1.6, "เช้าวันต่อมา ผ้าถุงบนราวเปียกชุ่ม... ทั้งที่ฝนไม่ได้ตก"),
    ("end", NARR, "-32%", "-14Hz", "-15%", "whisper", 1.6, "คืนนี้... คุณเก็บผ้าเข้าบ้านแล้วหรือยัง"),
]
FX = {
    "calm": "asetrate=24000*0.95,aresample=44100,atempo=1.0526,aecho=0.8:0.6:45|110:0.12|0.06",
    "tense": "asetrate=24000*0.93,aresample=44100,atempo=1.0753,aecho=0.8:0.65:50|120|210:0.16|0.09|0.05",
    "dread": "asetrate=24000*0.89,aresample=44100,atempo=1.1236,lowpass=f=5200,"
             "aecho=0.8:0.7:60|150|260:0.22|0.13|0.07",
    "whisper": "asetrate=24000*0.91,aresample=44100,atempo=1.0989,highpass=f=160,"
               "aecho=0.8:0.75:70|170|300:0.25|0.15|0.09",
    "granny": "asetrate=24000*0.9,aresample=44100,atempo=1.111,vibrato=f=5.5:d=0.18,"
              "aecho=0.8:0.5:40:0.08",
}
TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB,areverse")


# ---------------------------------------------------------------- voiceover
def tts():
    os.makedirs(TTS_DIR, exist_ok=True)
    clips = []
    for key, voice, rate, pitch, vol, style, _, text in SCRIPT:
        h = hashlib.md5(f"{voice}{rate}{pitch}{vol}{text}".encode()).hexdigest()[:10]
        mp3, wav = f"{TTS_DIR}/{key}_{h}.mp3", f"{TTS_DIR}/{key}_{h}_{style}.wav"
        if not os.path.exists(mp3) or os.path.getsize(mp3) == 0:
            cmd = ["edge-tts", "--voice", voice, f"--rate={rate}", f"--pitch={pitch}", f"--volume={vol}",
                   "--text", text, "--write-media", mp3]
            if os.environ.get("HTTPS_PROXY"):
                cmd += ["--proxy", os.environ["HTTPS_PROXY"]]
            for attempt in range(6):  # the TTS service fails intermittently
                if subprocess.run(cmd, capture_output=True).returncode == 0 and os.path.getsize(mp3) > 0:
                    break
                time.sleep(2 + attempt * 2)
            else:
                raise RuntimeError(f"TTS failed for {key}")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-af", f"{FX[style]},{TRIM}",
                        "-ac", "1", "-ar", str(SR), wav], check=True)
        with wave.open(wav) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
        clips.append(a / max(1e-6, np.abs(a).max()))
    return clips


CLIPS = tts()
T, cur = {}, 0.9
for (key, *_, gap, _txt), c in zip(SCRIPT, CLIPS):
    cur += gap
    T[key] = (cur, cur + len(c) / SR)
    cur = T[key][1]
JUMP = cur + 1.6          # final jump scare
DUR = math.ceil(JUMP + 1.2)
N = FPS * DUR
S = lambda k: T[k][0]  # noqa: E731
E = lambda k: T[k][1]  # noqa: E731
BLACK = (E("silent") + 0.5, S("reveal"))  # dead silence before the reveal
CLOSEUP = S("silent") - 0.3               # Ton's terrified close-up


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


def hrand(a, b):
    v = math.sin(a * 12.9898 + b * 78.233) * 43758.5453
    return v - math.floor(v) - 0.5


def jit(t, k, amp):
    return hrand(int(t * 8), k) * 2 * amp


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
        a = 1.4 * self.shake
        return SS * (x + jit(self.t, self.k, a)), SS * (y + jit(self.t, self.k + 500, a))

    def line(self, pts, col=None, w=None):
        pts = [self.p(*q) for q in pts]
        ww = max(1, int(SS * (w or self.w)))
        self.d.line(pts, fill=col or self.col, width=ww, joint="curve")
        for q in (pts[0], pts[-1]):
            self.d.ellipse([q[0] - ww / 2, q[1] - ww / 2, q[0] + ww / 2, q[1] + ww / 2], fill=col or self.col)

    def circle(self, x, y, r, col=None, fill=None, w=None):
        cx, cy = self.p(x, y)
        self.d.ellipse([cx - SS * r, cy - SS * r, cx + SS * r, cy + SS * r], outline=col or self.col,
                       fill=fill, width=max(1, int(SS * (w or self.w))))

    def ellipse(self, x, y, rx, ry, col=None, fill=None, w=None):
        cx, cy = self.p(x, y)
        self.d.ellipse([cx - SS * rx, cy - SS * ry, cx + SS * rx, cy + SS * ry], outline=col or self.col,
                       fill=fill, width=max(1, int(SS * (w or self.w))))

    def dot(self, x, y, r, col=None):
        cx, cy = self.p(x, y)
        self.d.ellipse([cx - SS * r, cy - SS * r, cx + SS * r, cy + SS * r], fill=col or self.col)

    def poly(self, pts, fill, outline=None):
        self.d.polygon([self.p(*q) for q in pts], fill=fill, outline=outline)


def pol(x, y, ang, ln):
    a = math.radians(ang)
    return x + ln * math.cos(a), y + ln * math.sin(a)


def face(pen, hx, hy, r, look, expr, t, eye_col=None):
    """Expressions: neutral, stern, worried, scared, terrified, sleep."""
    ex = hx + look * 0.25 * r
    sp = 0.35 * r
    w = max(2, r * 0.09)
    if expr == "sleep":
        for s in (-1, 1):
            pen.line([(ex + s * sp - 0.15 * r, hy), (ex + s * sp + 0.15 * r, hy + 0.04 * r)], w=w)
        return
    big = expr in ("scared", "terrified")
    for s in (-1, 1):
        x = ex + s * sp
        if big:
            er = 0.26 * r if expr == "terrified" else 0.21 * r
            pen.circle(x, hy, er, w=w * 0.8, fill=(250, 250, 245) if pen.col == INK else None)
            pr = 0.06 * r if expr == "terrified" else 0.09 * r
            pen.dot(x + look * 0.05 * r + jit(t * 3, s, 0.04 * r), hy + 0.02 * r, pr, col=eye_col or pen.col)
        else:
            pen.dot(x, hy, 0.11 * r, col=eye_col or pen.col)
        by = hy - (0.42 if big else 0.32) * r
        inner, outer = (x - s * 0.12 * r, x + s * 0.2 * r)
        if expr == "stern":
            pen.line([(outer, by - 0.08 * r), (inner, by + 0.06 * r)], w=w)
        elif expr in ("worried", "scared", "terrified"):
            pen.line([(outer, by + 0.05 * r), (inner, by - 0.1 * r)], w=w)
    my = hy + 0.45 * r
    if expr == "neutral":
        pen.line([(ex - 0.15 * r, my), (ex + 0.15 * r, my)], w=w)
    elif expr == "stern":
        pen.line([(ex - 0.22 * r, my + 0.04 * r), (ex, my), (ex + 0.22 * r, my + 0.04 * r)], w=w)
    elif expr == "worried":
        pen.line([(ex - 0.2 * r, my), (ex - 0.07 * r, my - 0.05 * r), (ex + 0.07 * r, my + 0.03 * r),
                  (ex + 0.2 * r, my - 0.02 * r)], w=w)
    else:
        o = 0.13 * r if expr == "scared" else 0.17 * r
        pen.ellipse(ex, my + 0.05 * r, o * 0.8, o * (1 + 0.15 * math.sin(t * 14)), w=w * 0.8)
    if big:  # sweat drops
        for k in range(2 if expr == "terrified" else 1):
            ph = (t * 0.7 + k * 0.5) % 1
            sx = hx - (1 if look >= 0 else -1) * (0.88 + 0.12 * k) * r
            sy = hy - 0.4 * r + ph * 0.9 * r
            pen.poly([(sx, sy - 0.16 * r), (sx - 0.08 * r, sy), (sx + 0.08 * r, sy)], fill=(140, 200, 255))
            pen.dot(sx, sy + 0.01 * r, 0.08 * r, col=(140, 200, 255))


def stickman(pen, x, y, s, arms=((120, 100), (60, 80)), legs=(105, 75), tilt=0, kind="kid", look=1,
             expr="neutral", t=0.0):
    """x,y = feet. Angles in degrees, 90 = straight down."""
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
    r = 0.2 * s
    hx, hy = head
    pen.circle(hx, hy, r)
    face(pen, hx, hy, r, look, expr, t)
    if kind == "kid":  # red cap = Ton's signature item
        pen.line([(hx - r, hy - 0.45 * r), (hx, hy - 1.05 * r), (hx + r, hy - 0.45 * r)], col=RED, w=6)
        pen.line([(hx + look * 0.7 * r, hy - 0.5 * r), (hx + look * 1.6 * r, hy - 0.45 * r)], col=RED, w=6)
    elif kind == "grandma":
        pen.circle(hx - look * 0.85 * r, hy - 0.8 * r, 0.4 * r)  # hair bun
    return head


def big_ton(pen, cx, cy, R, t, expr="terrified", look=0.3):
    pen.circle(cx, cy, R, w=8, fill=(14, 18, 24))
    face(pen, cx, cy + 0.08 * R, R, look, expr, t, eye_col=(20, 60, 40))
    pen.line([(cx - R * 1.02, cy - 0.45 * R), (cx, cy - 1.08 * R), (cx + R * 1.02, cy - 0.45 * R)], col=RED, w=16)
    pen.line([(cx + look * 0.6 * R, cy - 0.5 * R), (cx + look * 0.6 * R + 1.1 * R, cy - 0.42 * R)], col=RED, w=16)
    pen.line([(cx - 0.12 * R, cy + R), (cx - 0.12 * R, cy + 1.6 * R)], w=8)


def krasue(pen, x, y, s, t, wipe=0.0, eyes_open=1.0, grin=0.0, blinks=True):
    """Floating head with long hair; glowing strands hang below (stylized, no gore)."""
    for k in range(5):
        pts = [(x + (k - 2) * 0.09 * s + 0.06 * s * math.sin(t * 3 + j * 0.8 + k), y + 0.2 * s + j * 0.11 * s)
               for j in range(8)]
        pen.line(pts, col=(GREEN if k % 2 else (230, 110, 110)), w=max(3, s * 0.008))
    for k in range(-6, 7):
        if abs(k) < 3:
            continue
        side = 1 if k > 0 else -1
        pts = [(x + side * (0.12 * s + abs(k) * 0.018 * s + j * 0.012 * s) + 0.03 * s * math.sin(t * 2 + j * 0.6 + k),
                y - 0.15 * s + j * 0.09 * s) for j in range(10)]
        pen.line(pts, w=max(3, s * 0.008))
    pen.circle(x, y, 0.22 * s, fill=(18, 20, 26), w=max(4, s * 0.01))
    pen.line([(x - 0.2 * s, y - 0.08 * s), (x, y - 0.21 * s), (x + 0.2 * s, y - 0.08 * s)], w=max(5, s * 0.012))
    blink = 0.15 if blinks and (t % 3.3) < 0.1 else 1
    op = eyes_open * blink
    for ex in (-0.08, 0.08):
        if op < 0.2:
            pen.line([(x + ex * s - 0.035 * s, y), (x + ex * s + 0.035 * s, y)], col=GREEN, w=max(3, s * 0.008))
        else:
            pen.ellipse(x + ex * s, y, 0.04 * s, 0.04 * s * op, col=GREEN, fill=GREEN, w=1)
            pen.dot(x + ex * s, y, 0.012 * s, col=(10, 30, 15))
    m = 0.05 * s * (1 + wipe)
    if grin > 0:
        pen.line([(x - 0.08 * s, y + 0.1 * s), (x, y + 0.1 * s + 0.04 * s * grin), (x + 0.08 * s, y + 0.1 * s)],
                 col=(200, 90, 90), w=max(3, s * 0.008))
    else:
        pen.line([(x - m, y + 0.11 * s), (x + m, y + 0.12 * s)], col=(200, 90, 90), w=max(3, s * 0.008))


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


BG_NIGHT = bg((6, 9, 22), (20, 27, 40))
BG_DUSK = bg((36, 24, 54), (100, 62, 64))
BG_DAY = bg((200, 210, 216), (232, 226, 210))
BG_BLACK = bg((3, 4, 7), (9, 10, 14))
STARS = [(rng.integers(0, W), rng.integers(50, 380), rng.random()) for _ in range(90)]
yy, xx = np.ogrid[:H, :W]
VIGN = np.clip(1.25 - 0.75 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2), 0.15, 1)[..., None]


def stars(pen, t):
    for x, y, p in STARS:
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
    pen.line([(wx, base - 0.44 * h), (wx + 30, base - 0.44 * h), (wx + 30, base - 0.26 * h), (wx, base - 0.26 * h),
              (wx, base - 0.44 * h)], w=3)
    pen.line([(x - 30, base), (x + 10, base - 0.18 * h)], w=3)


def clothesline(pen, x0, x1, top, base, t, wet=0.0, swing=0.0, sarong_col=(150, 60, 70)):
    pen.line([(x0, base), (x0, top)])
    pen.line([(x1, base), (x1, top)])
    pen.line([(x0, top + 4), (x1, top + 8)], w=3)
    cx = (x0 + x1) / 2
    sw = 8 * math.sin(t * 1.3) + swing
    pen.poly([(cx - 50, top + 6), (cx + 50, top + 8), (cx + 48 + sw, top + 150), (cx - 48 + sw, top + 152)], fill=sarong_col)
    for k in range(1, 4):
        yy_ = top + 8 + k * 36
        pen.line([(cx - 49 + sw * k / 4, yy_), (cx + 49 + sw * k / 4, yy_ + 2)], col=(200, 120, 110), w=3)
    if wet > 0:
        pen.poly([(cx - 22 + sw * .5, top + 40), (cx + 25 + sw * .5, top + 45), (cx + 18 + sw, top + 150),
                  (cx - 15 + sw, top + 150)], fill=tuple(int(c * (1 - 0.5 * wet)) for c in sarong_col))
    return cx + sw, top + 150


_f = {}


def font(sz):
    if sz not in _f:
        _f[sz] = ImageFont.truetype(FONT, sz, layout_engine=ImageFont.Layout.RAQM)
    return _f[sz]


def text(img, s, y, sz, alpha, col=(240, 240, 230), stroke=4, dx=0):
    if alpha <= 0.01:
        return img
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    bb = d.textbbox((0, 0), s, font=font(sz), stroke_width=stroke, language="th")
    if bb[2] - bb[0] > W - 80:
        return text(img, s, y, int(sz * (W - 80) / (bb[2] - bb[0])), alpha, col, stroke, dx)
    d.text(((W - (bb[2] - bb[0])) // 2 - bb[0] + dx, y), s, font=font(sz), fill=col + (int(255 * alpha),),
           stroke_width=stroke, stroke_fill=(0, 0, 0, int(230 * alpha)), language="th")
    out = img.convert("RGBA")
    out.alpha_composite(lay)
    return out.convert("RGB")


# ---------------------------------------------------------------- scenes
GROUND = 560


def frame(i):
    t = i / FPS
    orbs, tint = [], None
    cam = (1.0, W / 2, H / 2)  # zoom, centre x, centre y (in 1x coords)
    shake = 0.0
    if t < S("intro") - 0.3:  # A: title + village, slow push in
        img = BG_NIGHT.copy(); pen = Pen(img, t)
        stars(pen, t)
        pen.circle(1060, 120, 34, fill=(220, 220, 200))
        pen.line([(0, GROUND), (W, GROUND)])
        house(pen, 160, GROUND, 220, 260, True)
        clothesline(pen, 820, 1060, 380, GROUND, t)
        for k in range(14):
            orbs.append((80 + k * 90 + 30 * math.sin(t + k), 600 + 40 * math.sin(t * 0.7 + k * 2), 6,
                         0.5 + 0.5 * math.sin(t * 3 + k), (150, 170, 40)))
        cam = (1.0 + 0.12 * smooth(0, S("intro"), t), W / 2, H / 2 + 20)
    elif t < S("forgot") - 0.3:  # B: grandma warns Ton; camera pushes in on her for the rule
        img = BG_DUSK.copy(); pen = Pen(img, t)
        pen.line([(0, GROUND), (W, GROUND)])
        house(pen, 40, GROUND, 200, 240, True)
        clothesline(pen, 960, 1200, 380, GROUND, t)
        rule = t > S("rule") - 0.2
        wag = 25 * math.sin(t * 7) if rule else 0
        g_arms = ((-10, -10), (110, 90)) if t > E("rule") - 0.6 else ((-40, -70 + wag), (110, 90))
        stickman(pen, 470, GROUND, 230, arms=g_arms, legs=(100, 82), tilt=12, kind="grandma",
                 expr="stern" if rule else "neutral", t=t)
        pen.line([(560, GROUND), (548, GROUND - 120)], w=4)
        ton_expr = "worried" if rule else "neutral"
        stickman(pen, 720, GROUND, 160, arms=((110, 95), (70, 85)), legs=(100, 80), kind="kid", look=-1,
                 expr=ton_expr, t=t)
        orbs.append((150, 430, 60, 0.35, (200, 140, 40)))  # warm window light
        z = smooth(S("warn"), S("rule") + 0.3, t)
        cam = (1.0 + 0.7 * z, W / 2 + (520 - W / 2) * z, H / 2 + (300 - H / 2) * z)
    elif t < S("clock") - 0.2:  # C: asleep, sarong forgotten outside; slow pan to sarong
        img = BG_NIGHT.copy(); pen = Pen(img, t)
        stars(pen, t)
        pen.line([(0, GROUND), (W, GROUND)])
        pen.line([(100, 250), (620, 250), (620, 470), (100, 470), (100, 250)])
        pen.line([(60, 250), (360, 110), (660, 250)])
        for px in (120, 300, 480, 600):
            pen.line([(px, 470), (px, GROUND)])
        pen.line([(160, 440), (420, 440)], w=3)
        pen.circle(190, 418, 18)
        face(pen, 190, 418, 18, 1, "sleep", t)
        pen.line([(208, 425), (360, 428)]); pen.line([(360, 428), (400, 438)]); pen.line([(250, 427), (300, 412)])
        pen.line([(172, 405), (190, 398), (208, 404)], col=RED, w=6)
        for k in range(3):
            ph = (t * 0.6 + k / 3) % 1
            pen.d.text((SS * (230 + ph * 60 + k * 10), SS * (390 - ph * 120)), "z", fill=CHALK, font=font(SS * (20 + 10 * k)))
        clothesline(pen, 860, 1100, 380, GROUND, t)
        pen.circle(1080, 110, 30, fill=(220, 220, 200))
        p = smooth(S("forgot") + 0.5, S("clock") - 0.2, t)
        cam = (1.15 + 0.35 * p, 380 + 600 * p, 380 + 60 * p)
    elif t < S("light") - 0.2:  # D: 02:17, startled awake
        img = BG_BLACK.copy(); pen = Pen(img, t)
        p = smooth(S("clock") + 1.2, E("clock") + 0.3, t)
        pen.line([(0, 520), (W, 520)], w=3)
        if p < 0.5:
            jolt = 6 * math.exp(-max(0, t - S("clock") - 1.2) * 6) * math.sin(t * 60)
            stickman(pen, 620 + jolt, 520, 150, arms=((80, 90), (100, 90)), legs=(0, 5),
                     tilt=-5 + 40 * (0.5 - p), kind="kid", expr="scared" if t > S("clock") + 1.2 else "sleep", t=t)
        else:
            x = 620 + (p - 0.5) * 500
            st = 18 * math.sin(t * 6)
            stickman(pen, x, 520, 150, arms=((90 + st, 95), (90 - st, 85)), legs=(90 + st, 90 - st), kind="kid",
                     expr="worried", t=t)
        orbs.append((W / 2, 300, 300, 0.06, (60, 80, 140)))
        cam = (1.3, 640 + 200 * p, 400)
    elif t < CLOSEUP:  # E: at the window, green light approaching; camera creeps toward the light
        img = BG_BLACK.copy(); pen = Pen(img, t)
        wx0, wy0, wx1, wy1 = 560, 120, 1200, 520
        pen.poly([(wx0, wy0), (wx1, wy0), (wx1, wy1), (wx0, wy1)], fill=(12, 20, 32))
        for x, y, ph in STARS[:40]:
            pen.dot(wx0 + (x % (wx1 - wx0)), wy0 + 10 + (y % 160), 1.2)
        hz = 340
        pen.line([(wx0, hz), (wx1, hz)], w=3)
        for k in range(1, 5):
            yk = hz + (wy1 - hz) * (k / 5) ** 1.5
            pen.line([(wx0, yk), (wx1, yk)], col=(70, 90, 80), w=2)
        pen.line([(wx0, wy0), (wx1, wy0), (wx1, wy1), (wx0, wy1), (wx0, wy0)], w=7)
        pen.line([((wx0 + wx1) / 2, wy0), ((wx0 + wx1) / 2, wy1)], w=5)
        p = smooth(S("light"), BLACK[0], t)
        lx = 1100 - 380 * p + 30 * math.sin(t * 0.9)
        ly = hz - 6 + 110 * p + 8 * math.sin(t * 2.2)
        fl = 0.85 + 0.15 * math.sin(t * 17) * math.sin(t * 5.3)
        orbs.append((lx, ly, 6 + 45 * p ** 1.6, smooth(S("light") - 0.2, S("light") + 0.8, t) * fl * (0.8 + 0.7 * p)))
        scared = t > S("closer")
        pen.shake = 1 + 1.5 * smooth(S("closer"), CLOSEUP, t)
        stickman(pen, 380, 560, 210, arms=((60, 20), (120, 160)) if not scared else ((40, -60), (140, 200)),
                 legs=(100, 80), kind="kid", look=1, expr="scared" if scared else "worried", t=t)
        tint = 0.25 * p
        q = smooth(S("light"), CLOSEUP, t)
        cam = (1.0 + 0.35 * q, W / 2 + 60 * q, H / 2 - 20 * q)
        shake = 2 * smooth(S("closer"), CLOSEUP, t)
    elif t < BLACK[0]:  # E2: terrified close-up, green light washing over his face, crickets stop
        img = BG_BLACK.copy(); pen = Pen(img, t, shake=2.5)
        u = smooth(CLOSEUP, BLACK[0], t)
        big_ton(pen, 600, 380, 230, t, "terrified", look=0.35)
        orbs.append((1240, 300, 260 + 120 * u, 0.35 + 0.5 * u))
        orbs.append((600 + 0.35 * 0.25 * 230 - 80, 398, 14, 0.6 + 0.4 * u))  # light reflected in eyes
        orbs.append((600 + 0.35 * 0.25 * 230 + 80, 398, 14, 0.6 + 0.4 * u))
        tint = 0.3 + 0.4 * u
        cam = (1.0 + 0.3 * u, 620, 380)
        shake = 3 + 3 * u
    elif t < S("wipe") - 0.2:  # F: blackout then reveal; eyes snap open
        img = BG_BLACK.copy(); pen = Pen(img, t)
        if t >= BLACK[1]:
            u = t - BLACK[1]
            sc = 420 + 260 * smooth(0, 0.35, u) + 80 * smooth(0.4, E("reveal") - BLACK[1] + 0.4, u)
            krasue(pen, W / 2, 230 + 8 * math.sin(t * 1.7), sc, t, eyes_open=smooth(0.9, 1.15, u))
            orbs.append((W / 2, 260, 240, 0.28))
            shake = 10 * math.exp(-u * 4) + (8 * math.exp(-(u - 0.95) * 6) if u > 0.95 else 0)
            tint = 0.2
    elif t < S("morning") - 0.4:  # G: it wipes its mouth on grandma's sarong; Ton peeks, terrified
        img = BG_NIGHT.copy(); pen = Pen(img, t)
        stars(pen, t)
        pen.line([(0, GROUND), (W, GROUND)])
        house(pen, 40, GROUND, 260, 300)
        px, py = 40 + 0.6 * 260 + 15, GROUND - 0.36 * 300
        pen.circle(px, py, 13, w=3)
        face(pen, px, py, 13, 1, "terrified", t)
        u = smooth(S("wipe") - 0.2, S("wipe") + 1.6, t)
        wipe = math.sin(t * 9) if t > S("wipe") + 2.2 else 0
        clothesline(pen, 640, 960, 330, GROUND, t, swing=-14 * abs(wipe) if wipe else 0)
        kx = 1200 - 400 * u + 22 * wipe
        ky = 300 + 16 * math.sin(t * 1.5)
        krasue(pen, kx, ky, 200, t, wipe=abs(wipe), grin=smooth(E("wipe") - 0.8, E("wipe"), t))
        orbs.append((kx, ky + 20, 90, 0.35))
        z = smooth(S("wipe") + 2.0, E("wipe") + 0.5, t)
        cam = (1.0 + 0.6 * z, W / 2 + (820 - W / 2) * z, H / 2 + (330 - H / 2) * z)
        tint = 0.12
    elif t < S("end") - 0.4:  # H: morning, the sarong is soaked
        img = BG_DAY.copy(); pen = Pen(img, t, col=INK)
        pen.line([(0, GROUND), (W, GROUND)])
        pen.circle(150, 120, 40, col=(230, 180, 60), fill=(250, 220, 120))
        sx, sy = clothesline(pen, 520, 840, 300, GROUND, t, wet=1.0)
        for k in range(3):
            ph = (t * 1.4 + k / 3) % 1
            pen.dot(sx - 15 + k * 15, sy + 10 + ph * (GROUND - sy - 10), 4, col=(120, 40, 50))
        stickman(pen, 300, GROUND, 220, arms=((70, 100), (110, 80)), legs=(100, 82), tilt=12, kind="grandma",
                 expr="worried", t=t)
        pen.line([(370, GROUND), (360, GROUND - 120)], w=4)
        stickman(pen, 1020, GROUND, 160, arms=((-150, -120), (-30, -60)), legs=(105, 75), kind="kid", look=-1,
                 expr="scared", t=t)
        z = smooth(S("morning") + 1.0, S("end") - 0.4, t)
        cam = (1.0 + 0.5 * z, W / 2 + (680 - W / 2) * z, H / 2 + (380 - H / 2) * z)
    elif t < JUMP:  # I: final line, eyes in the dark drift closer
        img = BG_BLACK.copy(); pen = Pen(img, t)
        u = smooth(S("end") + 0.8, JUMP, t)
        bl = (t % 2.7) < 0.12
        if not bl and t > S("end") + 0.8:
            sep = 18 + 30 * u
            for ex in (-sep, sep):
                pen.dot(1060 - 300 * u + ex, 150 + 60 * u, 5 + 6 * u, col=GREEN)
            orbs.append((1060 - 300 * u, 150 + 60 * u, 40 + 40 * u, 0.25 * smooth(S("end") + 0.8, S("end") + 1.8, t)))
    else:  # J: jump scare, then cut to black
        img = BG_BLACK.copy(); pen = Pen(img, t, shake=3)
        u = t - JUMP
        if u < 0.75:
            krasue(pen, W / 2, 330, 900 + 900 * smooth(0, 0.25, u), t, grin=1.0, blinks=False)
            orbs.append((W / 2, 330, 300, 0.4))
            shake = 14
            tint = 0.3
    # ----- camera: crop the 2x canvas
    z, cx, cy = cam
    cx += jit(t * 3, 901, shake); cy += jit(t * 3, 902, shake)
    vw, vh = W / z, H / z
    x0 = min(max(0, cx - vw / 2), W - vw); y0 = min(max(0, cy - vh / 2), H - vh)
    img = img.crop((int(x0 * SS), int(y0 * SS), int((x0 + vw) * SS), int((y0 + vh) * SS))).resize((W, H), Image.LANCZOS)
    a = np.asarray(img, float).copy()
    for o in orbs:
        x, y, r, inten = o[:4]
        orb(a, (x - x0) * z, (y - y0) * z, r * z, inten, *(o[4:] or [(40, 200, 110)]))
    if tint:
        a = a * (1 - 0.3 * tint) + tint * np.array([10, 70, 40])
    a *= VIGN if not (S("morning") - 0.4 <= t < S("end") - 0.4) else 0.85 + 0.15 * VIGN
    a += rng.normal(0, 4, (H, W, 1))
    fade = smooth(0, 0.8, t)
    if BLACK[0] <= t < BLACK[1] or t >= JUMP + 0.75:
        fade = 0
    img = Image.fromarray(np.clip(a * fade, 0, 255).astype(np.uint8))
    # ----- text
    if t < S("intro"):
        img = text(img, "ผีกระสือ", 220, 140, env(t, 0.6, S("intro") - 0.6, 0.5), (190, 255, 205), 7)
    for key, *_, line in SCRIPT:
        al = env(t, S(key), E(key) + 0.25, 0.2)
        if al <= 0:
            continue
        if key == "end":
            img = text(img, line, 300, 60, al, (220, 245, 228), 5, dx=int(jit(t * 2, 7, 2)))
        elif key == "rule":
            img = text(img, "ยาย: \"" + line + "\"", H - 110, 40, al, (255, 225, 170))
        else:
            img = text(img, line, H - 110, 40, al)
    if S("clock") - 0.2 <= t < S("light") - 0.2:
        img = text(img, "02:17", 40, 80, env(t, S("clock"), S("light") - 0.6, 0.4), (150, 240, 170), 4)
    return img


# ---------------------------------------------------------------- audio
def audio():
    n = SR * DUR
    ts = np.arange(n) / SR
    amb = np.zeros(n)

    def win(a, b, f=0.8):
        return np.clip((ts - a) / f, 0, 1) * np.clip((b - ts) / f, 0, 1)

    def tone(f, a, b, harm=5, att=1.2, rel=1.2, det=0.0):
        seg = (ts >= a) & (ts < b)
        tt = ts[seg] - a
        s = sum(np.sin(2 * np.pi * f * k * (1 + det) * tt) / k ** 1.6 for k in range(1, harm + 1))
        e = np.clip(tt / att, 0, 1) * np.clip((b - a - tt) / rel, 0, 1)
        out = np.zeros(n); out[seg] = s * e
        return out

    # dark minor pad through the story's quiet first half: Dm - Bb - Gm - A
    chords = [(146.8, 174.6, 220.0), (116.5, 146.8, 174.6), (98.0, 116.5, 146.8), (110.0, 138.6, 164.8)]
    st, k = 0.5, 0
    while st < S("clock"):
        for f in chords[k % 4]:
            amb += 0.045 * (tone(f, st, st + 4.3) + tone(f, st, st + 4.3, det=0.004))
        st += 4.0; k += 1
    # plucked tune (folk flavour) over the intro
    notes = [220, 262, 294, 330, 392, 440]
    for j, s0 in enumerate(np.arange(1.0, S("forgot") - 0.5, 1.2)):
        seg = (ts >= s0) & (ts < s0 + 1.2)
        tt = ts[seg] - s0
        amb[seg] += 0.07 * np.sin(2 * np.pi * notes[(j * 2 + j // 3) % 6] * tt) * np.exp(-tt * 3.5)
    # crickets: they stop together during "silent"
    c1 = np.sin(2 * np.pi * 4300 * ts) * (np.sin(2 * np.pi * 30 * ts) > 0.3) * (np.sin(2 * np.pi * 1.6 * ts) > 0)
    c2 = np.sin(2 * np.pi * 4700 * ts) * (np.sin(2 * np.pi * 26 * ts) > 0.4) * (np.sin(2 * np.pi * 1.1 * ts + 1) > 0.2)
    amb += (c1 + 0.7 * c2) * 0.03 * win(0.3, S("silent") + 1.8, 0.12)
    # wind
    wnd = np.convolve(rng.normal(0, 1, n), np.ones(400) / 400, mode="same") * 6
    amb += wnd * 0.1 * win(0, BLACK[0], 1.5)
    # clock ticks
    for s0 in np.arange(S("clock") - 0.6, S("light"), 1.0):
        seg = (ts >= s0) & (ts < s0 + 0.03)
        amb[seg] += 0.25 * np.sin(2 * np.pi * 2400 * (ts[seg] - s0)) * np.exp(-(ts[seg] - s0) * 150)
    # low drone + rising string cluster with tremolo, from the light until the blackout
    p = np.clip((ts - S("light")) / (BLACK[0] - S("light")), 0, 1)
    gate = win(S("clock") - 0.5, BLACK[0], 0.6) * (ts < BLACK[0])
    dr = np.sin(2 * np.pi * 55 * ts) + 0.6 * np.sin(2 * np.pi * 55.7 * ts) + 0.4 * np.sin(2 * np.pi * 82.4 * ts)
    amb += dr * (0.07 + 0.2 * p) * gate
    bend = 1 + 0.05 * p ** 2
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * (5 + 4 * p) * ts)
    cl = sum(np.sin(2 * np.pi * f * bend * ts) for f in (293.7, 311.1, 329.6, 440, 466.2))
    amb += 0.04 * cl * trem * p ** 1.5 * gate
    # heartbeat speeding up
    s0 = S("closer")
    while s0 < BLACK[0] - 0.2:
        for off, a_ in ((0, 1.0), (0.17, 0.7)):
            seg = (ts >= s0 + off) & (ts < s0 + off + 0.15)
            tt = ts[seg] - s0 - off
            amb[seg] += 0.38 * a_ * np.sin(2 * np.pi * 48 * tt) * np.exp(-tt * 30)
        s0 += 0.9 - 0.4 * (s0 - S("closer")) / max(1, BLACK[0] - S("closer"))
    # Ton's shaky breathing in the close-up
    br = np.convolve(rng.normal(0, 1, n), np.ones(30) / 30, mode="same")
    br = br - np.convolve(br, np.ones(300) / 300, mode="same")
    breath = np.clip(np.sin(2 * np.pi * ts / 1.1), 0, 1) ** 2
    amb += 0.9 * br * breath * win(CLOSEUP, BLACK[0], 0.3)
    # reveal sting
    seg = (ts >= BLACK[1]) & (ts < BLACK[1] + 4)
    tt = ts[seg] - BLACK[1]
    amb[seg] += 0.2 * sum(np.sin(2 * np.pi * f * tt) for f in (233, 247, 262, 466, 494)) * np.exp(-tt * 1.0)
    amb[seg] += 0.35 * rng.normal(0, 1, seg.sum()) * np.exp(-tt * 7)
    # second hit when the eyes open
    seg = (ts >= BLACK[1] + 0.95) & (ts < BLACK[1] + 2.5)
    tt = ts[seg] - BLACK[1] - 0.95
    amb[seg] += 0.25 * np.sin(2 * np.pi * 70 * tt) * np.exp(-tt * 3) + 0.1 * np.sin(2 * np.pi * 1760 * tt) * np.exp(-tt * 4)
    # eerie whine + low pulse while the head is on screen
    seg = (ts >= BLACK[1] + 0.5) & (ts < S("morning") - 0.4)
    tt = ts[seg] - BLACK[1]
    amb[seg] += 0.03 * np.sin(2 * np.pi * (1200 + 40 * np.sin(np.pi * tt)) * tt)
    amb[seg] += 0.08 * np.sin(2 * np.pi * 41 * tt) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.8 * tt))
    # morning birds + drips
    for s0 in np.arange(S("morning"), S("end") - 0.6, 0.8):
        seg = (ts >= s0) & (ts < s0 + 0.12)
        tt = ts[seg] - s0
        amb[seg] += 0.05 * np.sin(2 * np.pi * (2500 + 6000 * tt) * tt)
    for s0 in np.arange(S("morning") + 0.2, S("end") - 0.5, 0.5):
        seg = (ts >= s0) & (ts < s0 + 0.05)
        tt = ts[seg] - s0
        amb[seg] += 0.15 * np.sin(2 * np.pi * 900 * (1 - tt * 6) * tt) * np.exp(-tt * 80)
    # ending: low drone, single bell, then the jump-scare hit
    amb += 0.12 * np.sin(2 * np.pi * 49 * ts) * win(S("end") - 0.3, JUMP, 0.8)
    seg = (ts >= E("end") + 0.3) & (ts < JUMP)
    tt = ts[seg] - E("end") - 0.3
    amb[seg] += 0.2 * (np.sin(2 * np.pi * 880 * tt) + 0.5 * np.sin(2 * np.pi * 1320 * tt)) * np.exp(-tt * 2.2)
    seg = (ts >= JUMP) & (ts < JUMP + 0.9)
    tt = ts[seg] - JUMP
    amb[seg] += 0.6 * rng.normal(0, 1, seg.sum()) * np.exp(-tt * 5)
    amb[seg] += 0.4 * sum(np.sin(2 * np.pi * f * tt) for f in (196, 208, 277, 554)) * np.exp(-tt * 3)
    amb *= 0.5 / max(1e-6, np.abs(amb).max())
    # voiceover with per-line level
    vo = np.zeros(n)
    lvl = {"calm": 0.8, "tense": 0.85, "dread": 0.9, "whisper": 0.75, "granny": 0.85}
    for (key, *_r), c in zip(SCRIPT, CLIPS):
        a0 = int(S(key) * SR)
        vo[a0:a0 + len(c)] += c[: n - a0] * lvl[_r[4]]
    duck = 1 - 0.5 * np.convolve((np.abs(vo) > 0.02).astype(float), np.ones(4410) / 4410, mode="same")
    mix = vo + amb * duck
    mix = np.tanh(mix * 1.3) / np.tanh(1.3)  # gentle glue/compression
    mix *= 0.95 / np.abs(mix).max()
    stereo = np.stack([mix, 0.85 * mix + 0.15 * np.roll(amb * duck, 400)], 1)
    with wave.open("stick_audio.wav", "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(stereo, -1, 1) * 32767).astype(np.int16).tobytes())


def main():
    print(f"duration {DUR}s", {k: (round(a, 1), round(b, 1)) for k, (a, b) in T.items()}, flush=True)
    if PREVIEW:
        shots = [1.5, S("rule") + 1.2, S("forgot") + 1.5, S("clock") + 1.8, S("closer") + 1.2, CLOSEUP + 1.2,
                 S("reveal") + 1.4, S("wipe") + 3, S("morning") + 2, JUMP + 0.3]
        for k, tt in enumerate(shots):
            frame(int(tt * FPS)).save(f"sp_{k}.png")
        return
    audio()
    p = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-i", "stick_audio.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
    for i in range(N):
        p.stdin.write(frame(i).tobytes())
        if i % 240 == 0:
            print(f"frame {i}/{N}", flush=True)
    p.stdin.close(); p.wait()
    os.remove("stick_audio.wav")
    print("done", OUT)


if __name__ == "__main__":
    main()
