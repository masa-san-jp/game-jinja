"""Local image-gen client for a game server (game-jinja server.py etc.).

    from imggen_client import generate_image
    png_bytes = generate_image("a torii gate at dawn, anime game art")
    open("web/assets/torii.png", "wb").write(png_bytes)

One image is ~9s. Pre-generate into an asset pool at startup; do not call
on the hot path during play. Needs server.py running (default port 8771).
"""
import json
import os
import urllib.request

ENDPOINT = os.environ.get("IMGGEN_ENDPOINT", "http://127.0.0.1:8771") + "/generate"


def generate_image(prompt, width=720, height=720, seed=42, out_path=None):
    body = json.dumps({"prompt": prompt, "width": width, "height": height,
                       "seed": seed, "format": "png"}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(data)
    return data
