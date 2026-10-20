"""Builds profile.png from a public MyAnimeList list.
Usage: python generate.py [MAL_USERNAME]
"""
import io
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

USER = sys.argv[1] if len(sys.argv) > 1 else "THE-Eternity"
HERE = Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (mal-profile image generator)"}

W = 720
PAD = 40
COLS, GAP = 5, 16
CW = (W - 2 * PAD - (COLS - 1) * GAP) // COLS
CH = int(CW * 1.42)

SKY, LAV, ROSE, MINT, GOLD = "#8ecbff", "#b9a6ff", "#ff9ec7", "#7ee8c8", "#ffd98f"
TEXT, DIM = "#f4f6ff", "#b3bce3"


# ---------- fonts: repo fonts/ first (GitHub Actions), then Windows, then DejaVu ----------
def load_font(candidates, size):
    for c in candidates:
        name, var = c if isinstance(c, tuple) else (c, None)
        for base in (HERE / "fonts", Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu")):
            p = base / name
            if p.exists():
                f = ImageFont.truetype(str(p), size)
                if var:
                    try:
                        f.set_variation_by_name(var)
                    except Exception:
                        pass
                return f
    return ImageFont.load_default(size)


TITLE = load_font([("Cinzel.ttf", "Bold"), "palab.ttf", "DejaVuSerif-Bold.ttf"], 34)
HEAD = load_font([("Quicksand.ttf", "Bold"), "seguisb.ttf", "DejaVuSans-Bold.ttf"], 17)
BODY = load_font([("Quicksand.ttf", "SemiBold"), "seguisb.ttf", "DejaVuSans.ttf"], 13)
NUM = load_font([("Quicksand.ttf", "Bold"), "segoeuib.ttf", "DejaVuSans-Bold.ttf"], 22)
STAR = load_font(["DejaVuSans.ttf", "seguisym.ttf"], 11)
SMALL = load_font([("Quicksand.ttf", "SemiBold"), "segoeui.ttf", "DejaVuSans.ttf"], 11)


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def mal_list(status):
    items, offset = [], 0
    while True:
        url = f"https://myanimelist.net/animelist/{USER}/load.json?status={status}&offset={offset}"
        page = json.loads(get(url))
        items += page
        if len(page) < 300:
            return items
        offset += 300
        time.sleep(1)


def cover(url):
    url = url.split("?")[0].replace("/r/192x272", "").replace("/r/96x136", "")
    try:
        im = Image.open(io.BytesIO(get(url))).convert("RGB")
    except Exception:
        im = Image.new("RGB", (CW, CH), (30, 34, 70))
    s = max(CW / im.width, CH / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    l, t = (im.width - CW) // 2, (im.height - CH) // 2
    return im.crop((l, t, l + CW, t + CH))


def rgba(hex_, a):
    h = hex_.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def layer_rect(img, box, r, fill, outline=None, width=1):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).rounded_rectangle(box, r, fill=fill, outline=outline, width=width)
    img.alpha_composite(lay)


def pill_title(img, cx, y, text, font, color, pad=(22, 9)):
    d = ImageDraw.Draw(img)
    tw = d.textlength(text, font=font)
    asc, desc = font.getmetrics()
    box = (cx - tw / 2 - pad[0], y, cx + tw / 2 + pad[0], y + asc + desc + 2 * pad[1])
    layer_rect(img, box, (box[3] - box[1]) / 2, (10, 12, 32, 175), rgba(color, 110))
    d = ImageDraw.Draw(img)
    d.text((cx - tw / 2, y + pad[1] + 1), text, font=font, fill=(0, 0, 0, 150))
    d.text((cx - tw / 2, y + pad[1]), text, font=font, fill=color)
    return box[3]


def paste_cover(img, im, x, y, score=None):
    mask = Image.new("L", (CW, CH), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, CW - 1, CH - 1), 10, fill=255)
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x + 2, y + 6, x + CW + 2, y + CH + 6), 12, fill=(0, 0, 0, 140))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    img.paste(im, (x, y), mask)
    layer_rect(img, (x, y, x + CW - 1, y + CH - 1), 10, None, (190, 210, 255, 110))
    if score:
        col = GOLD if score >= 9 else MINT if score >= 7 else SKY if score >= 5 else ROSE
        t = str(score)
        d = ImageDraw.Draw(img)
        sw_ = d.textlength("★", font=STAR)
        tw = d.textlength(t, font=SMALL) + sw_ + 4
        bx = (x + CW - tw - 18, y + CH - 26, x + CW - 6, y + CH - 7)
        layer_rect(img, bx, 9, (10, 12, 32, 210), rgba(col, 160))
        d = ImageDraw.Draw(img)
        d.text((bx[0] + 6, bx[1] + 3), "★", font=STAR, fill=col)
        d.text((bx[0] + 6 + sw_ + 4, bx[1] + 3), t, font=SMALL, fill=col)


def main():
    completed = mal_list(2)
    watching = mal_list(1)
    everything = mal_list(7)
    completed.sort(key=lambda a: a.get("updated_at") or 0, reverse=True)
    watching.sort(key=lambda a: a.get("updated_at") or 0, reverse=True)

    scored = [a["score"] for a in completed if a.get("score")]
    stats = [
        ("Completed", str(len(completed)), SKY),
        ("Episodes", f"{sum(a.get('num_watched_episodes') or 0 for a in everything):,}", MINT),
        ("Mean Score", f"{sum(scored) / len(scored):.2f}" if scored else "–", GOLD),
        ("Plan to Watch", str(sum(1 for a in everything if a.get("status") == 6)), LAV),
    ]

    recent = completed[:10]
    watch = watching[:5]

    sig = json.dumps([[a["anime_id"], a.get("score")] for a in recent + watch] + [v for _, v, _ in stats])
    state = HERE / "state.json"
    if state.exists() and state.read_text() == sig and (HERE / "profile.png").exists():
        print("no change in list - skipping")
        return
    rows_recent = (len(recent) + COLS - 1) // COLS
    H = 110 + 92 + 60 + (CH + 20 if watch else 40) + 60 + rows_recent * (CH + GAP) + 50

    bg = Image.open(HERE / "bg.jpg").convert("RGB")
    s = max(W / bg.width, H / bg.height)
    bg = bg.resize((round(bg.width * s) + 1, round(bg.height * s) + 1), Image.LANCZOS)
    l, t = (bg.width - W) // 2, (bg.height - H) // 2
    img = bg.crop((l, t, l + W, t + H)).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (8, 10, 30, 125)))

    y = pill_title(img, W / 2, 28, USER, TITLE, "#ffffff", pad=(28, 10)) + 22

    # stats strip
    sw = (W - 2 * PAD - 3 * 12) / 4
    for i, (label, value, col) in enumerate(stats):
        x0 = PAD + i * (sw + 12)
        layer_rect(img, (x0, y, x0 + sw, y + 70), 16, (10, 12, 32, 165), rgba(col, 90))
        d = ImageDraw.Draw(img)
        vw = d.textlength(value, font=NUM)
        d.text((x0 + (sw - vw) / 2, y + 10), value, font=NUM, fill=col)
        lw = d.textlength(label, font=BODY)
        d.text((x0 + (sw - lw) / 2, y + 42), label, font=BODY, fill=DIM)
    y += 70 + 26

    # currently watching
    y = pill_title(img, W / 2, y, "Currently Watching", HEAD, SKY) + 16
    if watch:
        x = (W - (len(watch) * CW + (len(watch) - 1) * GAP)) // 2
        for a in watch:
            paste_cover(img, cover(a["anime_image_path"]), x, y)
            x += CW + GAP
        y += CH + 20
    else:
        d = ImageDraw.Draw(img)
        t = "taking a little break ~ nothing on the watchlist right now"
        d.text(((W - d.textlength(t, font=BODY)) / 2, y + 2), t, font=BODY, fill=DIM)
        y += 40

    # recently completed
    y = pill_title(img, W / 2, y + 4, "Recently Completed", HEAD, ROSE) + 16
    for r in range(rows_recent):
        row = recent[r * COLS:(r + 1) * COLS]
        x = (W - (len(row) * CW + (len(row) - 1) * GAP)) // 2
        for a in row:
            paste_cover(img, cover(a["anime_image_path"]), x, y, a.get("score") or None)
            x += CW + GAP
        y += CH + GAP

    d = ImageDraw.Draw(img)
    stamp = "updated " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    d.text(((W - d.textlength(stamp, font=SMALL)) / 2, H - 28), stamp, font=SMALL, fill=DIM)

    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), 24, fill=255)
    img.putalpha(mask)
    img.save(HERE / "profile.png", optimize=True)
    state.write_text(sig)
    print(f"profile.png {W}x{H}  completed={len(completed)} watching={len(watching)}")


if __name__ == "__main__":
    main()
