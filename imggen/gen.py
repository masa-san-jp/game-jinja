#!/usr/bin/env python3
"""Local image generation via ComfyUI on the DGX Spark.

Pays the model cold-load once, then every later call is the warm path.
Profiles pick the model/speed trade-off. Default = qwen-lightning (high quality).

Usage:
  gen.py "<prompt>" [--profile qwen-lightning|qwen-distill|sdxl-turbo]
                    [--width 720] [--height 720] [--seed N] [--out DIR]
  gen.py --warmup [--profile ...]   # load weights now, discard the image
Env: COMFY_HOST (default http://127.0.0.1:8188)
"""
import argparse
import json
import os
import sys
import time
import urllib.request

HOST = os.environ.get("COMFY_HOST", "http://127.0.0.1:8188")
OUTDIR = "/home/masa/dev/comfyui/output"

QWEN_CLIP = {"class_type": "CLIPLoader",
             "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                        "type": "qwen_image", "device": "default"}}
QWEN_VAE = {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}}


def qwen_lightning(prompt, w, h, seed):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_fp8_e4m3fn.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": "Qwen-Image-Lightning-8steps-V1.0.safetensors", "strength_model": 1.0}},
        "3": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["2", 0], "shift": 3.1}},
        "4": QWEN_CLIP,
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 0], "text": prompt}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 0], "text": ""}},
        "7": QWEN_VAE,
        "8": {"class_type": "EmptySD3LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "9": {"class_type": "KSampler", "inputs": {"model": ["3", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["8", 0], "seed": seed, "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["7", 0]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "gen_qwenL"}},
    }


def sdxl_turbo(prompt, w, h, seed):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_turbo_1.0_fp16.safetensors"}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": prompt}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": ""}},
        "8": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "9": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["8", 0], "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1.0}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["1", 2]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "gen_sdxlT"}},
    }


# sdxl-turbo requires sd_xl_turbo_1.0_fp16.safetensors (not yet downloaded — HF CDN was
# ~60KB/s on the hackathon network; pre-download on a faster link before using it).
PROFILES = {"qwen-lightning": qwen_lightning, "sdxl-turbo": sdxl_turbo}


def _post(path, obj):
    r = urllib.request.Request(HOST + path, data=json.dumps(obj).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=600))


def _get(path):
    return json.load(urllib.request.urlopen(HOST + path, timeout=60))


def generate(profile, prompt, w, h, seed):
    wf = PROFILES[profile](prompt, w, h, seed)
    t0 = time.time()
    pid = _post("/prompt", {"prompt": wf})["prompt_id"]
    while True:
        h2 = _get(f"/history/{pid}")
        st = h2.get(pid, {}).get("status", {})
        if st.get("completed"):
            break
        if st.get("status_str") == "error":
            raise RuntimeError(json.dumps(st, ensure_ascii=False)[:600])
        time.sleep(0.4)
    dt = time.time() - t0
    imgs = [os.path.join(OUTDIR, im.get("subfolder", ""), im["filename"])
            for _, d in h2[pid]["outputs"].items() for im in d.get("images", [])]
    return dt, imgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?", default="")
    ap.add_argument("--profile", default="qwen-lightning", choices=list(PROFILES))
    ap.add_argument("--width", type=int, default=720)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--warmup", action="store_true")
    args = ap.parse_args()
    if args.warmup:
        dt, imgs = generate(args.profile, "warmup", 256, 256, 1)
        print(f"[warmup] {args.profile} ready in {dt:.1f}s (cold load paid)")
        return
    if not args.prompt:
        print("error: prompt required", file=sys.stderr)
        sys.exit(2)
    dt, imgs = generate(args.profile, args.prompt, args.width, args.height, args.seed)
    print(f"{args.profile} {args.width}x{args.height}: {dt:.1f}s -> {imgs}")


if __name__ == "__main__":
    main()
