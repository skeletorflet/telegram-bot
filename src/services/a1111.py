import os
import base64
import aiohttp
import json
import logging
from pathlib import Path
from datetime import datetime

A1111_URL = os.environ.get("A1111_URL", "http://127.0.0.1:7860")
LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

def _log_api_call(phase: str, payload: dict | None = None, response: dict | None = None) -> None:
    try:
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "phase": phase,
        }
        if payload is not None:
            # Clean payload for logging (truncate large fields)
            clean_payload = payload.copy()
            if "image" in clean_payload and clean_payload["image"]:
                clean_payload["image"] = f"[BASE64_IMAGE_{len(clean_payload['image'])}_CHARS]"
            entry["payload"] = clean_payload
        if response is not None:
            entry["response"] = response
        line = json.dumps(entry, ensure_ascii=False)
        with open(LOG_DIR / "a1111.jsonl", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        logging.exception("Failed to write a1111 log")

async def a1111_get_json(path: str):
    url = f"{A1111_URL}{path}"
    logging.info(f"Getting JSON from: {url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

async def a1111_test_connection():
    """Test connection to A1111 API"""
    try:
        url = f"{A1111_URL}/sdapi/v1/extra-single-image"
        logging.info(f"Testing connection to A1111 API at: {url}")
        async with aiohttp.ClientSession() as session:
            # Test with a simple GET to see if endpoint exists
            async with session.get(url) as resp:
                logging.info(f"A1111 test response status: {resp.status}")
                if resp.status == 405:  # Method not allowed is expected for GET on POST endpoint
                    logging.info("A1111 API endpoint exists (405 Method Not Allowed is expected)")
                    return True
                elif resp.status == 404:
                    logging.error("A1111 API endpoint not found - check A1111_URL and ensure extra-single-image endpoint exists")
                    return False
                else:
                    logging.info(f"A1111 API test response: {resp.status}")
                    return True
    except Exception as e:
        logging.error(f"Failed to connect to A1111 API: {str(e)}")
        return False

async def fetch_samplers() -> list[str]:
    data = await a1111_get_json("/sdapi/v1/samplers")
    return [x.get("name") for x in data if isinstance(x, dict) and x.get("name")]

async def fetch_schedulers() -> list[dict]:
    data = await a1111_get_json("/sdapi/v1/schedulers")
    return [
        {"name": x.get("name"), "label": x.get("label") or x.get("name")}
        for x in data
        if isinstance(x, dict) and x.get("name")
    ]

async def fetch_loras() -> list[str]:
    data = await a1111_get_json("/sdapi/v1/loras")
    names = []
    for x in data:
        n = x.get("name") or x.get("model_name") or x.get("path")
        if n:
            names.append(n)
    return names

async def get_current_model() -> str | None:
    """Obtiene el nombre del checkpoint del modelo SD actual desde A1111."""
    try:
        options = await a1111_get_json("/sdapi/v1/options")
        model_name = options.get("sd_model_checkpoint")
        if model_name:
            logging.info(f"Modelo actual de A1111: {model_name}")
            return model_name
        else:
            logging.warning("No se pudo determinar el modelo actual desde /sdapi/v1/options")
            return None
    except Exception as e:
        logging.error(f"Error al obtener el modelo de A1111: {e}")
        return None

def _normalize_scheduler(scheduler: str | None) -> str | None:
    if not scheduler or str(scheduler).lower() in {"", "none", "automatic"}:
        return "Automatic"
    return scheduler

async def a1111_txt2img(prompt: str, width: int = 512, height: int = 512, steps: int = 4, cfg_scale: float = 1.0, sampler_name: str = "LCM", n_iter: int = 1, scheduler: str = "", seed: int = -1, negative_prompt: str = "", hr_options: dict | None = None) -> dict:
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": seed,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "width": width,
        "height": height,
        "sampler_name": sampler_name,
        "scheduler": _normalize_scheduler(scheduler),
        "batch_size": 1,
        "n_iter": max(1, min(8, n_iter)),
        "send_images": True,
        "save_images": False,
    }
    if hr_options:
        payload.update({
            "enable_hr": True,
            "hr_scale": hr_options.get("hr_scale", 1.5),
            "hr_second_pass_steps": hr_options.get("hr_second_pass_steps", max(1, steps // 2)),
            "hr_upscaler": hr_options.get("hr_upscaler", "R-ESRGAN 4x+"),
            "hr_scheduler": hr_options.get("hr_scheduler"),
            "hr_sampler_name": hr_options.get("hr_sampler_name"),
            "hr_prompt": hr_options.get("hr_prompt", ""),
            "hr_negative_prompt": hr_options.get("hr_negative_prompt", ""),
            "denoising_strength": hr_options.get("denoising_strength", 0.3),
        })
    url = f"{A1111_URL}/sdapi/v1/txt2img"
    async with aiohttp.ClientSession() as session:
        logging.info(f"txt2img payload: {payload}")
        _log_api_call("request", payload=payload)
        async with session.post(url, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            imgs = [base64.b64decode(b) for b in (data.get("images") or [])]
            info_raw = data.get("info")
            info = None
            try:
                info = json.loads(info_raw) if isinstance(info_raw, str) else info_raw
            except Exception:
                info = None
            response_log = {"parameters": data.get("parameters"), "info": info_raw}
            _log_api_call("response", response=response_log)
            return {"images": imgs, "parameters": data.get("parameters"), "info": info}

async def a1111_extra_single_image(image_bytes: bytes, upscaler_1: str = "R-ESRGAN 4x+", upscaling_resize: int = 2, upscaling_resize_w: int = 0, upscaling_resize_h: int = 0, upscaling_crop: bool = True) -> bytes:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "resize_mode": 0,
        "show_extras_results": True,
        "gfpgan_visibility": 0,
        "codeformer_visibility": 0,
        "codeformer_weight": 0,
        "upscaling_resize": upscaling_resize,
        "upscaling_crop": upscaling_crop,
        "upscaler_1": upscaler_1,
        "upscaler_2": "None",
        "extras_upscaler_2_visibility": 0,
        "upscale_first": False,
        "image": b64,
    }
    url = f"{A1111_URL}/sdapi/v1/extra-single-image"
    async with aiohttp.ClientSession() as session:
        logging.info(f"Llamando a extra-single-image con payload: upscaler={upscaler_1}, resize={upscaling_resize}, image_size={len(b64)} chars")
        _log_api_call("extras_request", payload=payload)
        try:
            async with session.post(url, json=payload) as resp:
                logging.info(f"Response status: {resp.status}")
                if resp.status != 200:
                    error_text = await resp.text()
                    logging.error(f"A1111 API Error Response: {error_text}")
                    resp.raise_for_status()
                
                data = await resp.json()
                logging.info(f"Response data keys: {list(data.keys()) if data else 'None'}")
                img_b64 = data.get("image")
                if not img_b64:
                    logging.warning(f"No 'image' key in response. Full response: {data}")
                    # Fallback for older API versions that might return "images"
                    images_list = data.get("images")
                    if images_list:
                        img_b64 = images_list[0]

                if not img_b64:
                    logging.error("Respuesta de A1111 no contiene imagen.")
                    _log_api_call("extras_response_error", response={"error": "No image in response", "response_preview": str(data)[:500]})
                    return b""

                out = base64.b64decode(img_b64)
                _log_api_call("extras_response", response={"ok": True, "has_image": True, "response_keys": list(data.keys()) if data else []})
                return out
        except Exception as e:
            logging.error(f"Error en extra-single-image: {str(e)}", exc_info=True)
            raise