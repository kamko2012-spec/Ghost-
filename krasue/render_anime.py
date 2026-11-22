"""ผีกระสือ — 7-scene horror clip in the skill's locked style:
minimalist hand-painted anime, pale white face, dot eyes, no mouth, signature red bandana #B3261E,
muted watercolor, cold blue-green palette, heavy fog, low-key light, film grain, no gore.

Needs: edge-tts (pip), ffmpeg, Loma Thai font, network access to speech.platform.bing.com.
Usage: python3 render_anime.py [out.mp4] [preview]
"""
import hashlib
import math
import os
import subprocess
import sys
import time
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, SR = 1280, 720, 24, 44100
CW, CH = 1536, 864  # canvas is 1.2x the frame so the camera can pan/zoom
FONT = "/usr/share/fonts/opentype/tlwg/Loma-Bold.otf"
OUT = sys.argv[1] if len(sys.argv) > 1 else "krasue_anime.mp4"
PREVIEW = len(sys.argv) > 2 and sys.argv[2] == "preview"
TTS_DIR = "tts_cache"
rng = np.random.default_rng(5)

# ---------------------------------------------------------------- character lock
BANDANA = (179, 38, 30)  # #B3261E — never changes
SKIN = (238, 238, 232)
HAIR = (18, 18, 22)
SHIRT = (168, 182, 186)
PANTS = (44, 48, 56)
CLOTH_A, CLOTH_B = (86, 128, 140), (205, 210, 200)  # motif: checkered pha khao ma

# ---------------------------------------------------------------- TTS director
NARR, GRAN = "th-TH-NiwatNeural", "th-TH-PremwadeeNeural"
# key, voice, rate, pitch, style(cue), pause before, text
SCRIPT = [
    ("hook", NARR, "-12%", "-6Hz", "mysterious", 0.0, "หมู่บ้านริมทุ่งในอีสาน มีกฎแปลกอยู่ข้อหนึ่ง... ห้ามตากผ้าทิ้งไว้ข้ามคืน"),
    ("ton", NARR, "-10%", "-5Hz", "calm", 1.0, "ต้น ครูอาสาจากกรุงเทพ มาพักอยู่บ้านยายบัว"),
    ("rule", GRAN, "-18%", "-16Hz", "granny", 0.6, "ลืมผ้าไว้ข้างนอกก็ช่างมัน... หลังเที่ยงคืน ห้ามออกไปเก็บเด็ดขาด"),
    ("doubt", NARR, "-12%", "-6Hz", "calm", 0.6, "ต้นพยักหน้า... แต่ในใจ เขาไม่เชื่อเลยสักนิด"),
    ("n1", NARR, "-14%", "-7Hz", "uneasy", 1.0, "คืนแรก มีแสงสีเขียว ลอยอยู่ไกลๆ กลางทุ่ง"),
    ("n2", NARR, "-15%", "-8Hz", "uneasy", 0.8, "คืนที่สอง ผ้าขาวม้าของเขา หล่นอยู่บนคันนา... เปียกชุ่ม"),
    ("n3", NARR, "-18%", "-9Hz", "tense", 0.8, "คืนที่สาม... แสงนั้น มาหยุดอยู่ที่ราวผ้า หน้าบ้าน"),
    ("out", NARR, "-22%", "-11Hz", "whisper", 0.9, "ต้นเปิดประตู... แล้วเดินออกไป"),
    ("face", NARR, "-22%", "-12Hz", "dread", 2.8, "หลังกอกล้วย มีใบหน้าผู้หญิงลอยอยู่... ใต้คาง ไม่มีร่างกาย"),
    ("wipe", NARR, "-22%", "-12Hz", "dread", 0.7, "มันกำลังเอาผ้าขาวม้าของเขา... เช็ดปาก"),
    ("after", GRAN, "-20%", "-16Hz", "granny", 1.6, "ครูคนก่อน ก็ออกไปเก็บผ้าตอนเที่ยงคืน... เหมือนเอ็งนั่นแหละ"),
    ("bag", NARR, "-15%", "-9Hz", "cold", 1.2, "วันที่ต้นกลับกรุงเทพ ผ้าขาวม้าผืนนั้น พับอยู่ในกระเป๋าของเขา... ยังเปียกอยู่"),
    ("end", NARR, "-22%", "-13Hz", "chill", 1.0, "ถ้าคืนนี้คุณลืมเก็บผ้า... พรุ่งนี้ลองนับดูนะ ว่ามีผืนไหน ที่ไม่ใช่ของคุณ"),
]
FX = {
    "mysterious": "asetrate=24000*0.94,aresample=44100,atempo=1.0638,aecho=0.8:0.6:50|120:0.14|0.07",
    "calm": "asetrate=24000*0.95,aresample=44100,atempo=1.0526,aecho=0.8:0.6:45|110:0.12|0.06",
    "uneasy": "asetrate=24000*0.94,aresample=44100,atempo=1.0638,aecho=0.8:0.62:50|130:0.15|0.08",
    "tense": "asetrate=24000*0.93,aresample=44100,atempo=1.0753,aecho=0.8:0.65:55|140|230:0.17|0.1|0.05",
    "whisper": "asetrate=24000*0.92,aresample=44100,atempo=1.087,highpass=f=170,aecho=0.8:0.75:70|170|300:0.25|0.15|0.09",
    "dread": "asetrate=24000*0.9,aresample=44100,atempo=1.111,lowpass=f=5200,aecho=0.8:0.7:60|150|260:0.22|0.13|0.07",
    "cold": "asetrate=24000*0.93,aresample=44100,atempo=1.0753,aecho=0.8:0.68:60|150:0.2|0.1",
    "chill": "asetrate=24000*0.9,aresample=44100,atempo=1.111,highpass=f=120,aecho=0.8:0.78:80|190|330:0.27|0.16|0.1",
    "granny": "asetrate=24000*0.9,aresample=44100,atempo=1.111,vibrato=f=5.5:d=0.18,aecho=0.8:0.5:40:0.08",
}
LEVEL = {"granny": 0.82, "whisper": 0.75, "chill": 0.78}
TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB,areverse")


def tts():
    os.makedirs(TTS_DIR, exist_ok=True)
    clips = []
    for key, voice, rate, pitch, style, _, text in SCRIPT:
        h = hashlib.md5(f"{voice}{rate}{pitch}{text}".encode()).hexdigest()[:10]
        mp3, wav = f"{TTS_DIR}/{key}_{h}.mp3", f"{TTS_DIR}/{key}_{h}_{style}.wav"
        if not os.path.exists(mp3) or os.path.getsize(mp3) == 0:
            cmd = ["edge-tts", "--voice", voice, f"--rate={rate}", f"--pitch={pitch}", "--text", text,
                   "--write-media", mp3]
            if os.environ.get("HTTPS_PROXY"):
                cmd += ["--proxy", os.environ["HTTPS_PROXY"]]
            for attempt in range(12):  # the TTS service fails intermittently (rate limiting)
                if subprocess.run(cmd, capture_output=True).returncode == 0 and os.path.getsize(mp3) > 0:
                    break
                time.sleep(4 + 3 * attempt)
            else:
                raise RuntimeError(f"TTS failed for {key}")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-af", f"{FX[style]},{TRIM}",
                        "-ac", "1", "-ar", str(SR), wav], check=True)
        with wave.open(wav) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
        clips.append(a / max(1e-6, np.abs(a).max()) * LEVEL.get(style, 0.85))
    return clips


CLIPS = tts()
T, cur = {}, 0.8
for (key, *_r), c in zip(SCRIPT, CLIPS):
    cur += _r[4]
    T[key] = (cur, cur + len(c) / SR)
    cur = T[key][1]
DUR = math.ceil(cur + 2.4)
N = FPS * DUR
S = lambda k: T[k][0]  # noqa: E731
E = lambda k: T[k][1]  # noqa: E731
SILENCE = (E("out") + 0.4, S("face") - 0.1)  # the 2-3 s of dead silence (scene 4)


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


def lowfreq(h, w, scale, seed):
    r = np.random.default_rng(seed)
    small = r.random((h // scale + 2, w // scale + 2))
    img = Image.fromarray((small * 255).astype(np.uint8)).resize(((w // scale + 2) * scale, (h // scale + 2) * scale),
                                                                 Image.BICUBIC)
    return np.asarray(img, float)[:h, :w] / 127.5 - 1


NOISE = 0.6 * lowfreq(CH, CW, 90, 1) + 0.4 * lowfreq(CH, CW, 25, 2)
PAPER = 1 - 0.05 * (0.5 + 0.5 * lowfreq(H, W, 6, 3)) - 0.04 * (0.5 + 0.5 * lowfreq(H, W, 2, 4))
yy, xx = np.ogrid[:H, :W]
VIGN = np.clip(1.25 - 0.8 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2), 0.12, 1)[..., None]


def fog_tex(scale, seed):
    r = np.random.default_rng(seed)
    small = r.random((H // scale + 3, 2 * W // scale))
    small = np.concatenate([small, small[:, :3]], axis=1)
    img = Image.fromarray((small * 255).astype(np.uint8)).resize(
        (small.shape[1] * scale, small.shape[0] * scale), Image.BICUBIC).filter(ImageFilter.GaussianBlur(scale * 0.6))
    return np.asarray(img, float)[:H, :2 * W] / 255.0


FOG1, FOG2 = fog_tex(110, 11), fog_tex(50, 12)


def fog(t, strength, tint=(150, 175, 178), speed=1.0):
    o1, o2 = int(t * 16 * speed) % W, int(t * 30 * speed) % W
    f = 0.6 * FOG1[:, o1:o1 + W] + 0.4 * FOG2[:, o2:o2 + W]
    ym = np.linspace(0.35, 1.0, H)[:, None]
    return (f * ym * strength)[..., None] * np.array(tint, float)


def paint(cv, mask, color, var=0.1, edge=0.3, alpha=1.0):
    """Watercolour wash: pigment variation + darker pooled edges."""
    m = np.asarray(mask.filter(ImageFilter.GaussianBlur(1.6)), float) / 255 * alpha
    b = np.asarray(mask.filter(ImageFilter.GaussianBlur(7)), float) / 255
    rim = np.clip(m - b, 0, 1) * edge
    col = np.array(color, float) * (1 + var * NOISE[..., None]) * (1 - rim[..., None])
    cv *= 1 - m[..., None]
    cv += col * m[..., None]


def newmask():
    m = Image.new("L", (CW, CH), 0)
    return m, ImageDraw.Draw(m)


def sky(top, bottom):
    y = np.linspace(0, 1, CH)[:, None, None]
    g = np.array(top, float) * (1 - y) + np.array(bottom, float) * y
    g = np.broadcast_to(g, (CH, CW, 3)).copy()
    return g * (1 + 0.06 * NOISE[..., None])


def treeline(cv, base, col, seed, amp=40):
    r = np.random.default_rng(seed)
    m, d = newmask()
    pts = [(0, CH)]
    for x in range(0, CW + 30, 30):
        pts.append((x, base - amp * 0.5 - amp * 0.5 * math.sin(x * 0.011 + seed) - r.random() * amp * 0.4))
    pts.append((CW, CH))
    d.polygon(pts, fill=255)
    paint(cv, m, col, edge=0.15)


def palm(cv, x, base, h, col):
    m, d = newmask()
    d.line([(x, base), (x + 10, base - h)], fill=255, width=7)
    for a in range(0, 360, 36):
        an = math.radians(a)
        d.line([(x + 10, base - h), (x + 10 + 70 * math.cos(an), base - h + 30 * math.sin(an) + 20)], fill=255, width=6)
    paint(cv, m, col, edge=0.1)


def stilt_house(cv, x, base, w, h, col, lit=True):
    m, d = newmask()
    d.rectangle([x, base - 0.55 * h, x + w, base - 0.2 * h], fill=255)
    d.polygon([(x - 0.12 * w, base - 0.55 * h), (x + w / 2, base - h), (x + 1.12 * w, base - 0.55 * h)], fill=255)
    for px in np.linspace(x + 6, x + w - 12, 5):
        d.rectangle([px, base - 0.2 * h, px + 7, base], fill=255)
    paint(cv, m, col, edge=0.2)
    if lit:
        m, d = newmask()
        d.rectangle([x + 0.62 * w, base - 0.48 * h, x + 0.62 * w + 26, base - 0.3 * h], fill=255)
        paint(cv, m, (210, 160, 80), edge=0.1)


def checker(d, x0, y0, x1, y1, sag=0.0, alpha=255):
    """The motif: faded checkered pha khao ma."""
    d.polygon([(x0, y0), (x1, y0), (x1 + sag, y1), (x0 + sag, y1)], fill=CLOTH_B + (alpha,))
    n = 6
    for k in range(n):
        if k % 2 == 0:
            xa = x0 + (x1 - x0) * k / n
            xb = x0 + (x1 - x0) * (k + 1) / n
            d.polygon([(xa, y0), (xb, y0), (xb + sag, y1), (xa + sag, y1)], fill=CLOTH_A + (int(alpha * 0.8),))
    for k in range(1, 5, 2):
        ya = y0 + (y1 - y0) * k / 5
        yb = y0 + (y1 - y0) * (k + 0.6) / 5
        s0, s1 = sag * k / 5, sag * (k + 0.6) / 5
        d.polygon([(x0 + s0, ya), (x1 + s0, ya), (x1 + s1, yb), (x0 + s1, yb)], fill=CLOTH_A[:3] + (int(alpha * 0.55),))


# ---------------------------------------------------------------- static backgrounds
def bg_village():
    cv = sky((14, 26, 38), (52, 74, 80))
    m, d = newmask(); d.ellipse([1180, 80, 1240, 140], fill=255); paint(cv, m, (205, 215, 200), edge=0.05)
    treeline(cv, 520, (26, 42, 46), 3, 50)
    palm(cv, 210, 520, 170, (22, 34, 38)); palm(cv, 1330, 520, 150, (22, 34, 38))
    m, d = newmask(); d.rectangle([0, 560, CW, CH], fill=255); paint(cv, m, (34, 52, 50), edge=0.1)
    stilt_house(cv, 300, 600, 260, 300, (20, 26, 30))
    m, d = newmask()
    for x in (780, 1060):
        d.rectangle([x, 430, x + 6, 600], fill=255)
    d.line([(782, 436), (1064, 442)], fill=255, width=3)
    paint(cv, m, (16, 20, 24), edge=0.05)
    for k in range(9):  # paddy lines
        m, d = newmask()
        y = 600 + (CH - 600) * (k / 9) ** 1.4
        d.line([(0, y), (CW, y + 4)], fill=255, width=2 + k // 3)
        paint(cv, m, (46, 66, 62), edge=0)
    return cv


def bg_porch():
    cv = sky((10, 14, 20), (30, 34, 40))
    m, d = newmask(); d.rectangle([0, 0, CW, 140], fill=255); paint(cv, m, (24, 22, 24), edge=0.2)  # floor above
    m, d = newmask()
    for x in (120, 620, 1120, 1450):
        d.rectangle([x, 120, x + 34, CH], fill=255)
    paint(cv, m, (44, 36, 34), edge=0.25)
    m, d = newmask(); d.rectangle([0, 700, CW, CH], fill=255); paint(cv, m, (52, 46, 40), edge=0.1)  # bamboo bed
    m, d = newmask()
    for k in range(0, CW, 46):
        d.line([(k, 700), (k + 10, CH)], fill=255, width=3)
    paint(cv, m, (38, 33, 30), edge=0)
    # oil lamp
    m, d = newmask(); d.rectangle([760, 640, 790, 700], fill=255); d.ellipse([755, 600, 795, 650], fill=255)
    paint(cv, m, (90, 70, 50), edge=0.2)
    return cv


def bg_field():
    cv = sky((8, 16, 26), (30, 48, 54))
    treeline(cv, 470, (20, 34, 38), 7, 30)
    m, d = newmask(); d.rectangle([0, 470, CW, CH], fill=255); paint(cv, m, (26, 42, 42), edge=0.05)
    for k in range(10):
        m, d = newmask()
        y = 470 + (CH - 470) * (k / 10) ** 1.5
        d.line([(0, y), (CW, y)], fill=255, width=2 + k // 3)
        paint(cv, m, (40, 60, 58), edge=0)
    # porch post + floor edge in foreground (Ton watches from the porch)
    m, d = newmask(); d.rectangle([0, 760, CW, CH], fill=255); d.rectangle([60, 0, 110, CH], fill=255)
    paint(cv, m, (14, 16, 18), edge=0.1)
    return cv


def bg_dyke():
    cv = sky((120, 140, 140), (160, 172, 166))
    treeline(cv, 380, (90, 110, 108), 9, 25)
    m, d = newmask(); d.rectangle([0, 380, CW, CH], fill=255); paint(cv, m, (96, 120, 112), edge=0.05)
    m, d = newmask(); d.polygon([(0, 640), (CW, 520), (CW, 640), (0, 790)], fill=255)  # the dyke path
    paint(cv, m, (120, 112, 96), edge=0.2)
    for k in range(40):  # rice stalks
        m, d = newmask()
        x = (k * 41) % CW
        y0 = 700 + (k * 37) % 160
        d.line([(x, y0), (x + 8, y0 - 70)], fill=255, width=3)
        paint(cv, m, (70, 100, 84), edge=0)
    return cv


def bg_window():
    cv = sky((6, 10, 16), (14, 20, 26))  # dark room
    m, d = newmask(); d.rectangle([520, 120, 1300, 640], fill=255)
    outside = sky((10, 20, 30), (30, 46, 50))
    mm = np.asarray(m, float)[..., None] / 255
    cv[:] = cv * (1 - mm) + outside * mm
    m, d = newmask()
    for x in (780, 1060):
        d.rectangle([x, 330, x + 6, 640], fill=255)
    d.line([(782, 336), (1064, 342)], fill=255, width=3)
    paint(cv, m, (12, 16, 20), edge=0.05)
    m, d = newmask()
    d.rectangle([500, 100, 1320, 130], fill=255); d.rectangle([500, 630, 1320, 660], fill=255)
    d.rectangle([500, 100, 530, 660], fill=255); d.rectangle([1290, 100, 1320, 660], fill=255)
    d.rectangle([900, 100, 920, 660], fill=255)
    paint(cv, m, (40, 34, 32), edge=0.25)
    return cv


def bg_door():
    cv = sky((6, 8, 12), (14, 16, 20))
    m, d = newmask(); d.rectangle([560, 160, 980, CH], fill=255)
    out = sky((14, 26, 34), (40, 58, 60))
    mm = np.asarray(m.filter(ImageFilter.GaussianBlur(2)), float)[..., None] / 255
    cv[:] = cv * (1 - mm) + out * mm
    m, d = newmask()
    d.rectangle([700, 420, 706, 700], fill=255); d.rectangle([900, 420, 906, 700], fill=255)
    d.line([(702, 426), (904, 430)], fill=255, width=3)
    paint(cv, m, (12, 16, 18), edge=0.05)
    m, d = newmask()
    d.rectangle([530, 140, 570, CH], fill=255); d.rectangle([970, 140, 1010, CH], fill=255); d.rectangle([530, 130, 1010, 170], fill=255)
    paint(cv, m, (40, 32, 30), edge=0.3)
    return cv


def bg_grove():
    cv = sky((6, 12, 16), (18, 30, 30))
    treeline(cv, 520, (14, 24, 24), 13, 60)
    m, d = newmask(); d.rectangle([0, 640, CW, CH], fill=255); paint(cv, m, (18, 26, 24), edge=0.05)
    for x, h in ((300, 420), (1200, 460), (820, 380)):  # banana trunks
        m, d = newmask(); d.polygon([(x - 22, 660), (x + 22, 660), (x + 12, 660 - h), (x - 12, 660 - h)], fill=255)
        paint(cv, m, (30, 44, 38), edge=0.25)
    return cv


def bg_room():
    cv = sky((96, 110, 116), (128, 132, 126))
    m, d = newmask(); d.rectangle([0, 620, CW, CH], fill=255); paint(cv, m, (110, 96, 80), edge=0.1)
    m, d = newmask(); d.rectangle([1040, 140, 1360, 420], fill=255); paint(cv, m, (190, 200, 196), edge=0.1)  # window light
    m, d = newmask(); d.rectangle([1190, 140, 1206, 420], fill=255); d.rectangle([1040, 272, 1360, 286], fill=255)
    paint(cv, m, (80, 70, 62), edge=0.1)
    for x in range(0, CW, 90):
        m, d = newmask(); d.line([(x, 0), (x, 620)], fill=255, width=3); paint(cv, m, (84, 96, 100), edge=0)
    return cv


def bg_bag():
    cv = sky((24, 28, 32), (40, 42, 44))
    m, d = newmask(); d.rectangle([0, 560, CW, CH], fill=255); paint(cv, m, (58, 52, 46), edge=0.1)
    m, d = newmask(); d.rounded_rectangle([420, 300, 1120, 760], 60, fill=255); paint(cv, m, (112, 100, 76), edge=0.3)
    m, d = newmask(); d.ellipse([470, 270, 1070, 420], fill=255); paint(cv, m, (26, 22, 20), edge=0.2)
    m, d = newmask(); d.arc([520, 120, 1020, 520], 200, 340, fill=255, width=22); paint(cv, m, (90, 78, 60), edge=0.2)
    return cv


print("painting backgrounds...", flush=True)
BGS = {k: Image.fromarray(np.clip(f(), 0, 255).astype(np.uint8)) for k, f in
       [("village", bg_village), ("porch", bg_porch), ("field", bg_field), ("dyke", bg_dyke), ("window", bg_window),
        ("door", bg_door), ("grove", bg_grove), ("room", bg_room), ("bag", bg_bag)]}


# ---------------------------------------------------------------- characters (drawn per frame on RGBA)
def pol(x, y, ang, ln):
    a = math.radians(ang)
    return x + ln * math.cos(a), y + ln * math.sin(a)


def limb(d, p0, a1, a2, ln, w, col):
    p1 = pol(*p0, a1, ln)
    p2 = pol(*p1, a2, ln)
    d.line([p0, p1, p2], fill=col, width=int(w), joint="curve")
    for p in (p0, p1, p2):
        d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=col)
    return p2


def ton(d, x, y, s, view="front", look=0.0, arms=((100, 95), (80, 85)), legs=((95, 92), (85, 88)), bag=False,
        tremble=0.0, t=0.0):
    """Ton: pale face, dot eyes, no mouth, messy black hair, red bandana (character lock)."""
    tx = tremble * math.sin(t * 40)
    hip = (x + tx, y - 0.47 * s)
    for (a1, a2), side in zip(legs, (-1, 1)):
        limb(d, (hip[0] + side * 0.04 * s, hip[1]), a1, a2, 0.24 * s, 0.075 * s, PANTS + (255,))
    sh_y = y - 0.77 * s
    d.polygon([(x - 0.12 * s + tx, sh_y), (x + 0.12 * s + tx, sh_y), (x + 0.09 * s + tx, hip[1] + 0.02 * s),
               (x - 0.09 * s + tx, hip[1] + 0.02 * s)], fill=SHIRT + (255,))
    for (a1, a2), side in zip(arms, (-1, 1)):
        hand = limb(d, (x + side * 0.11 * s + tx, sh_y + 0.02 * s), a1, a2, 0.17 * s, 0.06 * s, SHIRT + (255,))
        d.ellipse([hand[0] - 0.025 * s, hand[1] - 0.025 * s, hand[0] + 0.025 * s, hand[1] + 0.025 * s], fill=SKIN + (255,))
    if bag:
        d.rounded_rectangle([x + 0.1 * s + tx, y - 0.62 * s, x + 0.25 * s + tx, y - 0.42 * s], int(0.02 * s),
                            fill=(112, 100, 76, 255))
    hx, hy, r = x + tx + look * 0.02 * s, y - 0.9 * s, 0.105 * s
    d.ellipse([hx - 0.03 * s, sh_y - 0.06 * s, hx + 0.03 * s, sh_y + 0.01 * s], fill=SKIN + (255,))  # neck
    if view == "back":
        d.ellipse([hx - r, hy - 1.1 * r, hx + r, hy + r], fill=HAIR + (255,))
        d.line([(hx - 0.07 * s, sh_y - 0.01 * s), (hx + 0.07 * s, sh_y - 0.01 * s)], fill=BANDANA + (255,), width=int(0.03 * s))
        return
    d.ellipse([hx - r, hy - 1.1 * r, hx + r, hy + r], fill=SKIN + (255,))
    # messy hair cap
    pts = [(hx - 1.08 * r, hy - 0.05 * r)]
    for k in range(9):
        a = math.pi + k * math.pi / 8
        rr = 1.22 * r if k % 2 else 1.02 * r
        pts.append((hx + rr * math.cos(a), hy - 0.25 * r + rr * math.sin(a) * 1.05))
    pts += [(hx + 1.08 * r, hy - 0.05 * r), (hx + 0.5 * r, hy - 0.45 * r), (hx - 0.1 * r, hy - 0.3 * r),
            (hx - 0.6 * r, hy - 0.5 * r)]
    d.polygon(pts, fill=HAIR + (255,))
    er = 0.1 * r
    eyes = (-1, 1) if view == "front" else (1,)
    for sd in eyes:
        ex = hx + (sd * 0.38 * r if view == "front" else look * 0.5 * r) + look * 0.2 * r
        d.ellipse([ex - er, hy + 0.15 * r - er, ex + er, hy + 0.15 * r + er], fill=(20, 20, 24, 255))
    # bandana knot — the signature item
    d.polygon([(hx - 0.075 * s, sh_y - 0.03 * s), (hx + 0.075 * s, sh_y - 0.03 * s), (hx, sh_y + 0.06 * s)],
              fill=BANDANA + (255,))
    d.ellipse([hx - 0.02 * s, sh_y - 0.035 * s, hx + 0.02 * s, sh_y + 0.005 * s], fill=(150, 30, 24, 255))


def granny(d, x, y, s, look=1.0, arm_raise=0.0, t=0.0):
    hip = (x, y - 0.42 * s)
    d.polygon([(x - 0.13 * s, hip[1]), (x + 0.13 * s, hip[1]), (x + 0.15 * s, y), (x - 0.15 * s, y)], fill=(66, 48, 66, 255))
    sh = (x + look * 0.06 * s, y - 0.7 * s)
    d.polygon([(sh[0] - 0.11 * s, sh[1]), (sh[0] + 0.11 * s, sh[1]), (x + 0.12 * s, hip[1] + 0.03 * s),
               (x - 0.12 * s, hip[1] + 0.03 * s)], fill=(178, 170, 158, 255))
    wag = 12 * math.sin(t * 6) * arm_raise
    hand = limb(d, (sh[0] + look * 0.09 * s, sh[1] + 0.02 * s), 90 - look * 70 * arm_raise,
                90 - look * 110 * arm_raise + wag, 0.15 * s, 0.05 * s, (178, 170, 158, 255))
    d.ellipse([hand[0] - 0.02 * s, hand[1] - 0.02 * s, hand[0] + 0.02 * s, hand[1] + 0.02 * s], fill=SKIN + (255,))
    limb(d, (sh[0] - look * 0.09 * s, sh[1] + 0.02 * s), 100, 80, 0.15 * s, 0.05 * s, (178, 170, 158, 255))
    hx, hy, r = sh[0] + look * 0.05 * s, sh[1] - 0.12 * s, 0.09 * s
    d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=SKIN + (255,))
    d.chord([hx - 1.05 * r, hy - 1.1 * r, hx + 1.05 * r, hy + 0.6 * r], 180, 360, fill=(196, 196, 190, 255))
    d.ellipse([hx - look * 0.9 * r - 0.5 * r, hy - 1.3 * r, hx - look * 0.9 * r + 0.5 * r, hy - 0.4 * r], fill=(196, 196, 190, 255))
    er = 0.1 * r
    for sd in (-1, 1):
        ex = hx + sd * 0.35 * r + look * 0.25 * r
        d.ellipse([ex - er, hy + 0.12 * r - er, ex + er, hy + 0.12 * r + er], fill=(20, 20, 24, 255))
    d.line([(x + look * 0.24 * s, y), (x + look * 0.2 * s, y - 0.5 * s)], fill=(70, 56, 44, 255), width=int(0.025 * s))


def krasue(d, glow, x, y, s, t, reveal=1.0, wipe=0.0):
    """Half-hidden: pale face, long hair over half the face, one eye, no body (soft glow below)."""
    a = int(255 * reveal)
    for k in range(6):
        pts = [(x + (k - 2.5) * 0.06 * s + 0.04 * s * math.sin(t * 2.5 + j * 0.7 + k), y + 0.18 * s + j * 0.09 * s)
               for j in range(9)]
        glow.line(pts, fill=((120, 255, 170) if k % 2 else (230, 120, 120)) + (int(a * 0.8),), width=int(0.025 * s))
    glow.ellipse([x - 0.25 * s, y + 0.15 * s, x + 0.25 * s, y + 0.6 * s], fill=(60, 220, 140, int(a * 0.16)))
    d.ellipse([x - 0.16 * s, y - 0.2 * s, x + 0.16 * s, y + 0.2 * s], fill=(214, 224, 214, a))
    er = 0.018 * s
    d.ellipse([x + 0.06 * s - er, y - 0.01 * s - er, x + 0.06 * s + er, y - 0.01 * s + er], fill=(14, 30, 20, a))
    sw = 0.02 * s * math.sin(t * 2)
    d.chord([x - 0.17 * s, y - 0.23 * s, x + 0.17 * s, y - 0.09 * s], 180, 360, fill=(10, 10, 12, a))  # crown
    d.polygon([(x - 0.02 * s, y - 0.2 * s), (x - 0.05 * s, y + 0.12 * s), (x - 0.08 * s + sw, y + 0.8 * s),
               (x - 0.27 * s + sw, y + 0.8 * s), (x - 0.25 * s, y + 0.05 * s), (x - 0.18 * s, y - 0.2 * s)],
              fill=(10, 10, 12, a))  # curtain over the left half of the face
    d.polygon([(x + 0.155 * s, y - 0.1 * s), (x + 0.2 * s + sw, y + 0.65 * s), (x + 0.25 * s + sw, y + 0.65 * s),
               (x + 0.2 * s, y - 0.13 * s)], fill=(10, 10, 12, a))  # strands at the right edge
    if wipe > 0:
        dx = 0.05 * s * math.sin(t * 7) * wipe
        checker(d, x - 0.08 * s + dx, y + 0.07 * s, x + 0.2 * s + dx, y + 0.3 * s, sag=0.03 * s, alpha=a)


def leaves(d, t, col=(16, 30, 24, 255)):
    for cx, cy, ang, ln in ((700, 520, -20, 420), (980, 600, 200, 460), (540, 560, -10, 330), (420, 760, -35, 380)):
        a = math.radians(ang + 3 * math.sin(t * 0.8 + cx))
        pts = []
        for k in range(13):
            u = k / 12
            w = math.sin(u * math.pi) * 0.22 * ln
            px, py = cx + u * ln * math.cos(a), cy + u * ln * math.sin(a)
            pts.append((px - w * math.sin(a), py + w * math.cos(a)))
        for k in range(12, -1, -1):
            u = k / 12
            w = math.sin(u * math.pi) * 0.22 * ln * (0.6 + 0.4 * ((k * 7) % 3 / 2))
            px, py = cx + u * ln * math.cos(a), cy + u * ln * math.sin(a)
            pts.append((px + w * math.sin(a), py - w * math.cos(a)))
        d.polygon(pts, fill=col)


# ---------------------------------------------------------------- frame
_f = {}


def font(sz):
    if sz not in _f:
        _f[sz] = ImageFont.truetype(FONT, sz, layout_engine=ImageFont.Layout.RAQM)
    return _f[sz]


def text(img, s, y, sz, alpha, col=(232, 236, 230), stroke=3, x=None):
    if alpha <= 0.01:
        return img
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    bb = d.textbbox((0, 0), s, font=font(sz), stroke_width=stroke, language="th")
    if bb[2] - bb[0] > W - 80:
        return text(img, s, y, int(sz * (W - 80) / (bb[2] - bb[0])), alpha, col, stroke, x)
    px = (W - (bb[2] - bb[0])) // 2 - bb[0] if x is None else x
    d.text((px, y), s, font=font(sz), fill=col + (int(255 * alpha),), stroke_width=stroke,
           stroke_fill=(0, 0, 0, int(200 * alpha)), language="th")
    out = img.convert("RGBA")
    out.alpha_composite(lay)
    return out.convert("RGB")


def frame(i):
    t = i / FPS
    lay = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    gl = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    d, g = ImageDraw.Draw(lay), ImageDraw.Draw(gl)
    orbs = []  # (x, y, r, intensity, colour) in canvas coords
    cam = (1.0, CW / 2, CH / 2)
    fog_s, fog_speed, grade = 0.25, 1.0, 1.0
    label = None
    if t < S("ton") - 0.3:  # 1 HOOK: village at night, the cloth on the line
        key = "village"
        lay2 = ImageDraw.Draw(lay)
        sw = 6 * math.sin(t * 1.2)
        checker(lay2, 860, 446, 960, 560, sag=sw)
        u = smooth(0, S("ton"), t)
        cam = (1.0 + 0.45 * u, CW / 2 + (900 - CW / 2) * u, CH / 2 + (500 - CH / 2) * u)
        orbs.append((300 + 0.62 * 260 + 13, 600 - 0.39 * 300, 40, 0.25, (210, 150, 60)))
        fog_s = 0.35
    elif t < S("n1") - 0.3:  # 2 SETUP: porch, oil lamp, grandma warns, Ton doubts
        key = "porch"
        speaking = S("rule") - 0.2 < t < E("rule") + 0.2
        granny(d, 560, 790, 330, look=1, arm_raise=1.0 if speaking else 0.0, t=t)
        arrive = smooth(S("ton"), S("ton") + 2.2, t)
        tx = 1500 - 470 * arrive
        walking = arrive < 1
        st = 18 * math.sin(t * 7) if walking else 0
        ton(d, tx, 800, 420, view="front", look=-0.8 if not walking else -1,
            legs=((90 + st, 90), (90 - st, 90)), bag=True, t=t)
        fl = 0.9 + 0.1 * math.sin(t * 11) * math.sin(t * 3.7)
        orbs.append((775, 600, 220, 0.42 * fl, (220, 150, 60)))
        orbs.append((775, 610, 18, 0.9 * fl, (255, 200, 120)))
        if t < S("rule") - 0.2:
            cam = (1.05, CW / 2 + 60, CH / 2 + 40)
        elif t < E("rule") + 0.3:
            u = smooth(S("rule") - 0.2, S("rule") + 1.0, t)
            cam = (1.05 + 0.45 * u, CW / 2 + 60 + (600 - CW / 2 - 60) * u, CH / 2 + 40 + (520 - CH / 2 - 40) * u)
        else:
            u = smooth(E("rule") + 0.3, E("rule") + 1.3, t)
            cam = (1.5 + 0.2 * u, 600 + 430 * u, 520 - 20 * u)
        fog_s, grade = 0.12, 0.95
    elif t < S("n2") - 0.3:  # 3a ESCALATION night 1: distant green light, Ton from behind on the porch
        key, label = "field", "คืนที่ 1"
        ton(d, 330, 900, 520, view="back")
        fl = 0.8 + 0.2 * math.sin(t * 13) * math.sin(t * 4.1)
        orbs.append((1180 + 30 * math.sin(t * 0.7), 455 + 6 * math.sin(t * 2), 10, 1.0 * fl, (60, 220, 130)))
        u = smooth(S("n1") - 0.3, S("n2"), t)
        cam = (1.05 + 0.2 * u, CW / 2 + 40 * u, CH / 2 - 10 * u)
        fog_s = 0.3
    elif t < S("n3") - 0.3:  # 3b night 2: dawn mist, the cloth soaked on the dyke (motif #2)
        key, label = "dyke", "คืนที่ 2"
        checker(d, 700, 600, 880, 650, sag=-30)
        for k in range(3):
            ph = (t * 0.9 + k / 3) % 1
            d.ellipse([740 + k * 40, 652 + ph * 40, 748 + k * 40, 662 + ph * 40], fill=(70, 96, 104, int(200 * (1 - ph))))
        u = smooth(S("n2") - 0.3, S("n3"), t)
        cam = (1.2 + 0.35 * u, 800, 620)
        fog_s, grade = 0.45, 1.0
    elif t < S("out") - 0.3:  # 3c night 3: the light stops at the clothesline; Ton frozen inside
        key, label = "window", "คืนที่ 3"
        checker(d, 860, 346, 960, 460, sag=3 * math.sin(t))
        ton(d, 330, 920, 600, view="side", look=1, arms=((95, 90), (85, 90)), tremble=1.5, t=t)
        p = smooth(S("n3"), E("n3"), t)
        fl = 0.85 + 0.15 * math.sin(t * 17) * math.sin(t * 5.3)
        orbs.append((1300 - 330 * p, 330 + 40 * p, 14 + 30 * p, (0.7 + 0.5 * p) * fl, (60, 220, 130)))
        cam = (1.0 + 0.25 * smooth(S("n3"), S("out"), t), CW / 2 + 80, CH / 2)
        fog_s = 0.18
    elif t < S("face") - 0.1:  # 4 TURNING POINT: he walks out; then everything stops
        key = "door"
        u = smooth(S("out") + 0.6, E("out") + 0.4, t)
        walking = u < 1
        st = 14 * math.sin(t * 5) if walking else 0
        ton(d, 770, 1000 - 220 * u, 620 - 330 * u, view="back", legs=((90 + st, 90), (90 - st, 90)))
        orbs.append((800, 400, 60, 0.35, (60, 220, 130)))
        if t >= SILENCE[0]:
            fog_speed = 0.0  # the world holds its breath
        cam = (1.0 + 0.3 * smooth(S("out"), S("face"), t), 770, 520)
        fog_s = 0.25
    elif t < S("after") - 0.4:  # 5 CONFRONTATION: half-hidden face behind banana leaves
        key = "grove"
        rev = smooth(S("face") + 0.3, S("face") + 2.5, t)
        wipe = smooth(S("wipe") - 0.2, S("wipe") + 0.8, t)
        kx, ky = 900 + 10 * math.sin(t * 0.9), 330 + 8 * math.sin(t * 1.4)
        krasue(d, g, kx, ky, 600, t, reveal=rev, wipe=wipe)
        leaves(d, t)
        ton(d, 230, 1080, 700, view="back", arms=((70, 30), (100, 95)))
        flick = 1.0 if (math.sin(t * 23) * math.sin(t * 7.1)) > -0.55 else 0.15  # phone torch flickers
        orbs.append((360, 560, 260, 0.22 * flick, (190, 210, 220)))
        orbs.append((kx, ky + 240, 150, 0.14 * rev, (60, 220, 130)))
        cam = (1.15 + 0.35 * smooth(S("face"), E("wipe"), t), 820, 420)
        fog_s, grade = 0.22, 0.95
    elif t < S("bag") - 0.4:  # 6 AFTERMATH: morning, wrapped in a blanket; grandma speaks
        key = "room"
        bx, by = 980, 700
        d.rounded_rectangle([bx - 170, by - 260, bx + 170, by + 60], 120, fill=(128, 96, 78, 255))
        d.ellipse([bx - 70, by - 380, bx + 70, by - 230], fill=SKIN + (255,))
        d.chord([bx - 76, by - 400, bx + 76, by - 280], 180, 360, fill=HAIR + (255,))
        for sd in (-1, 1):
            d.ellipse([bx + sd * 26 - 6, by - 300 - 6, bx + sd * 26 + 6, by - 300 + 6], fill=(20, 20, 24, 255))
        d.polygon([(bx - 30, by - 232), (bx + 30, by - 232), (bx, by - 200)], fill=BANDANA + (255,))
        granny(d, 560, 800, 380, look=1, t=t)
        cam = (1.1 + 0.25 * smooth(S("after") - 0.4, S("bag"), t), 760, 470)
        fog_s, grade = 0.1, 1.0
    else:  # 7 FINAL STING: the cloth folded inside his bag, still wet (motif #3)
        key = "bag"
        checker(d, 600, 330, 940, 400, sag=10)
        for k in range(4):
            ph = (t * 0.8 + k / 4) % 1
            d.ellipse([560 + k * 120, 770 + ph * 60, 570 + k * 120, 782 + ph * 60], fill=(70, 96, 104, int(220 * (1 - ph))))
        u = smooth(S("bag") - 0.4, DUR, t)
        cam = (1.1 + 0.6 * u, 770, 420 + 40 * u)
        fog_s = 0.12
        grade = 1.0 - 0.75 * smooth(S("end") - 0.3, S("end") + 0.8, t)
    # compose: background + softened character layer + glow
    img = BGS[key].copy().convert("RGBA")
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(1.1)))
    if gl.getbbox():
        img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(14)))
    z, cx, cy = cam
    vw, vh = CW / z, CH / z
    x0 = min(max(0, cx - vw / 2), CW - vw); y0 = min(max(0, cy - vh / 2), CH - vh)
    img = img.convert("RGB").crop((int(x0), int(y0), int(x0 + vw), int(y0 + vh))).resize((W, H), Image.BICUBIC)
    a = np.asarray(img, float).copy()
    k = W / vw
    for ox, oy, r, inten, col in orbs:
        x, y, rr = (ox - x0) * k, (oy - y0) * k, r * k
        X0, X1, Y0, Y1 = max(0, int(x - 3 * rr)), min(W, int(x + 3 * rr)), max(0, int(y - 3 * rr)), min(H, int(y + 3 * rr))
        if X1 > X0 and Y1 > Y0:
            gy, gx = np.ogrid[Y0:Y1, X0:X1]
            d2 = ((gx - x) ** 2 + (gy - y) ** 2) / (rr * rr)
            a[Y0:Y1, X0:X1] += (np.exp(-d2)[..., None] * np.array(col) + np.exp(-d2 * 14)[..., None] * 200) * inten
    a += fog(t, fog_s, speed=fog_speed)
    a = a * PAPER[..., None]
    a = a * np.array([0.9, 1.0, 1.02]) + np.array([0, 4, 6])  # cold blue-green grade
    a *= VIGN
    a += rng.normal(0, 6, (H, W, 1))  # film grain
    fade = smooth(0, 1.0, t) * (1 - smooth(DUR - 1.0, DUR, t)) * grade
    img = Image.fromarray(np.clip(a * fade, 0, 255).astype(np.uint8))
    # on-screen text
    if t < S("ton") - 0.3:
        img = text(img, "ผีกระสือ", 200, 120, env(t, 0.6, 2.3, 0.5),
                   (205, 232, 214), 5)
        img = text(img, "ห้ามตากผ้าข้ามคืน", 200, 80, env(t, 3.4, S("ton") - 0.5, 0.4), (222, 236, 228), 4)
    if label:
        img = text(img, label, 50, 44, 0.85, (200, 222, 210), 3, x=70)
    for key_, voice, *_r, line in SCRIPT:
        al = env(t, S(key_), E(key_) + 0.25, 0.2)
        if al <= 0:
            continue
        if key_ == "end":
            img = text(img, line, 310, 46, al, (222, 240, 230), 4)
        else:
            img = text(img, ("ยายบัว: " if voice == GRAN else "") + line, H - 100, 36, al,
                       (250, 228, 190) if voice == GRAN else (236, 236, 230))
    return img


# ---------------------------------------------------------------- audio (BGM per scene)
def audio():
    n = SR * DUR
    ts = np.arange(n) / SR
    amb = np.zeros(n)

    def win(a, b, f=0.8):
        return np.clip((ts - a) / f, 0, 1) * np.clip((b - ts) / f, 0, 1)

    noise = rng.normal(0, 1, n)
    wind = np.convolve(noise, np.ones(500) / 500, mode="same") * 7
    # 1: low drone + light wind
    drone = np.sin(2 * np.pi * 55 * ts) + 0.5 * np.sin(2 * np.pi * 55.6 * ts) + 0.3 * np.sin(2 * np.pi * 82.5 * ts)
    amb += 0.12 * drone * win(0, S("ton") + 0.5, 1.5)
    amb += 0.14 * wind * (0.6 + 0.4 * np.sin(2 * np.pi * 0.08 * ts)) * win(0, SILENCE[0], 1.5)
    # 2: folk — phin plucks + khaen-like reed drone, crickets & frogs
    khaen = sum(np.sin(2 * np.pi * 220 * k * ts) / k for k in (1, 3, 5, 7)) + 0.6 * np.sin(2 * np.pi * 329.6 * ts)
    amb += 0.025 * khaen * (0.8 + 0.2 * np.sin(2 * np.pi * 0.5 * ts)) * win(S("ton") - 0.5, S("n1"), 1.2)
    notes = [220, 247, 294, 330, 392, 440, 494]
    for j, s0 in enumerate(np.arange(S("ton"), S("n1") - 0.6, 0.6)):
        if j % 4 == 3:
            continue
        seg = (ts >= s0) & (ts < s0 + 0.9)
        tt = ts[seg] - s0
        f = notes[(j * 3 + j // 5) % 7]
        amb[seg] += 0.07 * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt * 4.5)
    crick = (np.sin(2 * np.pi * 4300 * ts) * (np.sin(2 * np.pi * 30 * ts) > 0.3) * (np.sin(2 * np.pi * 1.6 * ts) > 0)
             + 0.7 * np.sin(2 * np.pi * 4700 * ts) * (np.sin(2 * np.pi * 26 * ts) > 0.4) * (np.sin(2 * np.pi * 1.1 * ts + 1) > 0.2))
    amb += 0.028 * crick * win(0.5, S("out") + 1.0, 0.2) * (1 - 0.6 * np.clip((ts - S("n2")) / max(1, S("out") - S("n2")), 0, 1))
    for s0 in np.arange(S("ton"), S("n2"), 0.73):  # frogs
        seg = (ts >= s0) & (ts < s0 + 0.09)
        tt = ts[seg] - s0
        amb[seg] += 0.05 * np.sin(2 * np.pi * (300 - 900 * tt) * tt) * (np.sin(2 * np.pi * 60 * tt) > 0)
    # 3: everything thins out until only breathing is left
    p = np.clip((ts - S("n1")) / max(1, S("out") - S("n1")), 0, 1)
    amb += 0.1 * drone * p * win(S("n1"), SILENCE[0], 1.0)
    br = np.convolve(noise, np.ones(30) / 30, mode="same")
    br = br - np.convolve(br, np.ones(300) / 300, mode="same")
    amb += 0.9 * br * np.clip(np.sin(2 * np.pi * ts / 1.3), 0, 1) ** 2 * win(S("n3"), SILENCE[0], 0.6) * (0.4 + 0.6 * p)
    # door creak at "out"
    seg = (ts >= S("out") + 0.5) & (ts < S("out") + 1.6)
    tt = ts[seg] - S("out") - 0.5
    amb[seg] += 0.08 * np.sin(2 * np.pi * (180 + 60 * np.sin(2 * np.pi * 1.5 * tt)) * tt) * (np.sin(2 * np.pi * 35 * tt) > 0) * np.exp(-tt * 1.5)
    amb[(ts >= SILENCE[0]) & (ts < SILENCE[1])] = 0  # 4: dead silence
    # 5: low trembling tone rising slowly, then cut
    a0, a1 = S("face"), E("wipe") + 0.3
    q = np.clip((ts - a0) / (a1 - a0), 0, 1)
    trem = 0.55 + 0.45 * np.sin(2 * np.pi * (4 + 5 * q) * ts)
    low = sum(np.sin(2 * np.pi * f * (1 + 0.04 * q) * ts) for f in (49, 73.4, 77.8, 146.8, 155.6))
    gate = (ts >= a0) & (ts < a1)
    amb += 0.07 * low * trem * (0.25 + 0.75 * q) * gate
    # 6: quiet room tone + faint morning birds
    amb += 0.03 * wind * win(S("after") - 0.4, S("bag"), 0.6)
    for s0 in np.arange(S("after"), S("bag") - 0.5, 1.1):
        seg = (ts >= s0) & (ts < s0 + 0.1)
        tt = ts[seg] - s0
        amb[seg] += 0.025 * np.sin(2 * np.pi * (2600 + 5000 * tt) * tt)
    # 7: drips, then one soft bell at the very end
    for s0 in np.arange(S("bag") + 0.3, S("end"), 0.7):
        seg = (ts >= s0) & (ts < s0 + 0.05)
        tt = ts[seg] - s0
        amb[seg] += 0.12 * np.sin(2 * np.pi * 950 * (1 - 6 * tt) * tt) * np.exp(-tt * 80)
    amb += 0.08 * drone * win(S("bag"), DUR - 0.2, 1.0)
    seg = ts >= E("end") + 0.4
    tt = ts[seg] - E("end") - 0.4
    amb[seg] += 0.22 * (np.sin(2 * np.pi * 880 * tt) + 0.45 * np.sin(2 * np.pi * 1318 * tt)) * np.exp(-tt * 1.6)
    amb *= 0.45 / max(1e-6, np.abs(amb).max())
    vo = np.zeros(n)
    for (key, *_), c in zip(SCRIPT, CLIPS):
        a = int(S(key) * SR)
        vo[a:a + len(c)] += c[: n - a]
    duck = 1 - 0.5 * np.convolve((np.abs(vo) > 0.02).astype(float), np.ones(4410) / 4410, mode="same")
    mix = vo + amb * duck
    mix = np.tanh(mix * 1.3) / np.tanh(1.3)
    mix *= 0.95 / np.abs(mix).max()
    st = np.stack([mix, 0.85 * mix + 0.15 * np.roll(amb * duck, 400)], 1)
    with wave.open("anime_audio.wav", "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(st, -1, 1) * 32767).astype(np.int16).tobytes())


def main():
    print(f"duration {DUR}s", {k: (round(a, 1), round(b, 1)) for k, (a, b) in T.items()}, flush=True)
    if PREVIEW:
        shots = [3.0, S("rule") + 1.5, E("doubt") - 0.3, S("n1") + 1.5, S("n2") + 1.5, S("n3") + 2,
                 S("out") + 1.5, S("face") + 2.5, S("wipe") + 1.5, S("after") + 1.5, S("bag") + 2, S("end") + 1]
        for k, tt in enumerate(shots):
            frame(int(tt * FPS)).save(f"ap_{k:02d}.png")
        return
    audio()
    p = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-i", "anime_audio.wav", "-vf", "hqdn3d=1.5:1:3:3", "-c:v", "libx264", "-preset", "slow",
         "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT],
        stdin=subprocess.PIPE)
    for i in range(N):
        p.stdin.write(frame(i).tobytes())
        if i % 240 == 0:
            print(f"frame {i}/{N}", flush=True)
    p.stdin.close(); p.wait()
    os.remove("anime_audio.wav")
    print("done", OUT)


if __name__ == "__main__":
    main()
