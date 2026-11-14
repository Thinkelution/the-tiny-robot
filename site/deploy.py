"""Deploys thetinyrobot.online (Cloudflare R2 bucket thetinyrobot-website on the apex domain).

  python site/deploy.py            build images from the renders, upload site/, purge the cache
  python site/deploy.py --images   only rebuild site/img from the renders

First run creates the bucket, connects thetinyrobot.online as its custom domain, adds a rule so folder paths serve
their index.html, and a www -> apex redirect. Token: the `cloudfflare` line in the keys file named by
CF_KEYS (default F:/work/keys.txt), never printed.
"""
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
REVIEW = ROOT / "films/the-tiny-robot/cast/review"
BUCKET = "thetinyrobot-website"
HOST = "thetinyrobot.online"
CAST = ["tiny", "mossback", "quota", "ledger", "shine", "warden", "dash", "primly"]
TYPES = {".html": "text/html; charset=utf-8", ".jpg": "image/jpeg", ".png": "image/png", ".mp4": "video/mp4",
         ".css": "text/css", ".js": "text/javascript; charset=utf-8", ".ico": "image/x-icon"}


def build_images():
    img = SITE / "img"
    (img / "cast").mkdir(parents=True, exist_ok=True)
    lineup = Image.open(REVIEW / "lineup.png").convert("RGB")
    lineup.save(img / "lineup.jpg", quality=88, optimize=True, progressive=True)
    lineup.resize((1200, 675), Image.LANCZOS).save(img / "og.jpg", quality=86)
    for rid in CAST:
        strip = Image.open(REVIEW / f"{rid}_turn.png").convert("RGB")
        s = strip.height
        strip.crop((s, 0, 2 * s, s)).resize((720, 720), Image.LANCZOS).save(img / "cast" / f"{rid}.jpg", quality=86)
    faces = Image.open(REVIEW / "tiny_faces.png").convert("RGB")
    w, h = faces.size
    # 3 x 2 grid of the six expressions, square-ish for the story panel
    cell = w // 6
    grid = Image.new("RGB", (cell * 3, h * 2))
    for k in range(6):
        grid.paste(faces.crop((k * cell, 0, (k + 1) * cell, h)), ((k % 3) * cell, (k // 3) * h))
    grid.resize((900, int(900 * grid.height / grid.width)), Image.LANCZOS).save(img / "tiny-faces.jpg", quality=86)
    # icon: the Tiny Robot's face
    tiny = Image.open(REVIEW / "tiny_faces.png").convert("RGB").crop((cell * 2, 0, cell * 3, h))
    side = min(tiny.size)
    tiny.crop(((tiny.width - side) // 2, 0, (tiny.width + side) // 2, side)).resize((192, 192), Image.LANCZOS) \
        .save(img / "icon.png")
    print("images built")


def token():
    keys = Path(os.environ.get("CF_KEYS", "F:/work/keys.txt"))
    line = next(l for l in keys.open(encoding="utf-8", errors="ignore") if l.lower().startswith("cloudfflare"))
    return re.split(r"[:=]", line, 1)[1].strip()


def api(method, path, body=None, ctype="application/json"):
    data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
    req = urllib.request.Request("https://api.cloudflare.com/client/v4" + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {TOK}", "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"success": False, "http": e.code, **json.loads(e.read() or b"{}")}


def setup(acc, zid):
    names = [b["name"] for b in api("GET", f"/accounts/{acc}/r2/buckets")["result"]["buckets"]]
    if BUCKET not in names:
        r = api("POST", f"/accounts/{acc}/r2/buckets", {"name": BUCKET})
        print("bucket:", "created" if r.get("success") else json.dumps(r)[:300])
    doms = api("GET", f"/accounts/{acc}/r2/buckets/{BUCKET}/domains/custom").get("result", {}).get("domains", [])
    if HOST not in [d.get("domain") for d in doms]:
        r = api("POST", f"/accounts/{acc}/r2/buckets/{BUCKET}/domains/custom",
                {"domain": HOST, "zoneId": zid, "enabled": True, "minTLS": "1.2"})
        print("custom domain:", "connected" if r.get("success") else json.dumps(r)[:300])
    # rules in this zone only; create each phase's entry ruleset when missing
    def phase_rules(phase):
        r = api("GET", f"/zones/{zid}/rulesets/phases/{phase}/entrypoint")
        return r.get("result", {}).get("rules", []) if r.get("success") else []

    def put_phase(phase, rules):
        r = api("PUT", f"/zones/{zid}/rulesets/phases/{phase}/entrypoint", {"rules": rules})
        return r.get("success"), r

    tr = phase_rules("http_request_transform")
    if not any("index.html" in json.dumps(x) for x in tr):
        ok, r = put_phase("http_request_transform", [_clean(x) for x in tr] + [{
            "description": "folder to its index.html", "action": "rewrite", "enabled": True,
            "expression": f'(http.host eq "{HOST}") and ends_with(http.request.uri.path, "/")',
            "action_parameters": {"uri": {"path": {"expression": 'concat(http.request.uri.path, "index.html")'}}}}])
        print("index rule:", "added" if ok else json.dumps(r)[:300])
    # www -> apex: a proxied DNS record so the hostname resolves, plus a redirect rule
    recs = api("GET", f"/zones/{zid}/dns_records?name=www.{HOST}")["result"]
    if not recs:
        r = api("POST", f"/zones/{zid}/dns_records", {"type": "AAAA", "name": "www", "content": "100::",
                                                      "proxied": True, "comment": "www redirects to the apex"})
        print("www record:", "added" if r.get("success") else json.dumps(r)[:300])
    rd = phase_rules("http_request_dynamic_redirect")
    if not any("www." in x.get("expression", "") for x in rd):
        ok, r = put_phase("http_request_dynamic_redirect", [_clean(x) for x in rd] + [{
            "description": "www to apex", "action": "redirect", "enabled": True,
            "expression": f'(http.host eq "www.{HOST}")',
            "action_parameters": {"from_value": {"status_code": 301, "preserve_query_string": True, "target_url": {
                "expression": f'concat("https://{HOST}", http.request.uri.path)'}}}}])
        print("www redirect:", "added" if ok else json.dumps(r)[:300])


def _clean(rule):
    return {k: rule[k] for k in ("description", "action", "enabled", "expression", "action_parameters") if k in rule}


def upload(acc, key, path):
    ctype = TYPES.get(path.suffix.lower()) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    r = api("PUT", f"/accounts/{acc}/r2/buckets/{BUCKET}/objects/{key}", path.read_bytes(), ctype)
    if not r.get("success", False):
        sys.exit(f"upload {key} failed: {json.dumps(r)[:300]}")


if __name__ == "__main__":
    build_images()
    if "--images" in sys.argv:
        sys.exit()
    TOK = token()
    z = api("GET", f"/zones?name={HOST}")["result"][0]
    acc, zid = z["account"]["id"], z["id"]
    setup(acc, zid)
    files = [p for p in SITE.rglob("*") if p.is_file() and p.suffix != ".py"]
    for p in files:
        key = p.relative_to(SITE).as_posix()
        upload(acc, key, p)
        print(f"  {key}  {p.stat().st_size // 1024} KB", flush=True)
    urls = [f"https://{HOST}/{p.relative_to(SITE).as_posix()}" for p in files] + [f"https://{HOST}/"]
    for i in range(0, len(urls), 30):
        api("POST", f"/zones/{zid}/purge_cache", {"files": urls[i:i + 30]})
    print(f"{len(files)} files -> https://{HOST}/")
