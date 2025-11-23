
import os
import asyncio
import logging
import base64
import json
import random
from pathlib import Path
from io import BytesIO
import aiohttp
from typing import Union
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from jobqueue.jobs import JobQueue, GenJob
import re
from services.a1111 import (
    a1111_extra_single_image, 
    get_current_model, 
    a1111_test_connection, 
    fetch_sd_models, 
    set_sd_model,
    fetch_samplers,
    fetch_schedulers,
    fetch_loras,
    fetch_adetailer_models,
    a1111_txt2img
)
from utils.formatting import FormatText, format_welcome_message, format_queue_status, format_generation_complete, format_error_message, format_settings_updated
from utils.prompt_generator import prompt_generator
from utils.process_manager import process_manager
from storage.jobs import save_job, get_job, delete_job
from pressets.pressets import Preset, get_preset_for_model
from ui.menus import (
    main_menu_keyboard, 
    submenu_keyboard_static, 
    loras_page_keyboard, 
    modifiers_page_keyboard,
    adetailer_page_keyboard
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Crear archivo de log para debugging de callbacks
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
CALLBACK_LOG_FILE = LOG_DIR / "callback_debug.jsonl"

def log_callback_payload(payload: dict):
    """Guarda payload de callback en archivo JSONL para debugging"""
    try:
        with open(CALLBACK_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as e:
        logging.error(f"Error guardando log de callback: {e}")

from config import A1111_URL
BOT_TOKEN_DEFAULT = os.environ.get("BOT_TOKEN", "7126310269:AAGiMx_x9jZzOpMWzoKFYfV82-YSx2oG44w")

USER_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "users"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SETTINGS = {
    "sampler_name": "LCM",
    "scheduler": "",
    "steps": 4,
    "cfg_scale": 1.0,
    "aspect_ratio": "1:1",
    "base_size": 512,
    "n_iter": 1,
    "pre_modifiers": [],
    "post_modifiers": [],
    "loras": [],
}

JOBQ = JobQueue(concurrency=2)

PRE_MODIFIERS = [
    "masterpiece, best quality", "ultra-detailed, intricate details", "4k, 8k, uhd",
    "photorealistic, realistic", "cinematic, movie still", "anime style, vibrant colors",
    "concept art, digital painting", "illustration, sharp focus", "low poly, isometric",
    "minimalist, simple background", "epic composition, dramatic", "golden hour, soft light",
    "vivid, saturated colors", "monochrome, black and white", "surreal, dreamlike",
    "fantasy, magical", "sci-fi, futuristic", "steampunk, mechanical details",
    "cyberpunk, neon lights", "vintage, retro style", "watercolor painting",
    "oil painting, classic", "sketch, charcoal drawing", "cel-shaded, cartoonish",
    "flat design, vector art", "hdr, high dynamic range", "long exposure, motion blur",
    "macro photography, close-up", "double exposure", "glitch effect, distorted"
]

POST_MODIFIERS = [
    "cinematic lighting", "dramatic shadows", "volumetric lighting, god rays",
    "studio lighting, softbox", "rim lighting, backlight", "neon glow, vibrant",
    "underwater lighting, caustic effects", "fire and embers", "lens flare, anamorphic",
    "bokeh, shallow depth of field", "highly detailed background", "simple background, clean",
    "fog, mist, atmospheric", "rain, wet surface", "snow, winter scene",
    "starry night sky", "aurora borealis", "reflections, reflective surface",
    "dynamic angle, action shot", "fisheye lens", "vignette, dark corners",
    "color grading, cinematic tones", "film grain, noisy", "light leaks, vintage effect",
    "chromatic aberration", "bloom, soft glow", "particle effects, dust motes",
    "sun rays, crepuscular rays", "glowing eyes", "smoke, atmospheric"
]




POST_MODIFIERS = [
    "cinematic lighting", "dramatic shadows", "volumetric lighting, god rays",
    "studio lighting, softbox", "rim lighting, backlight", "neon glow, vibrant",
    "underwater lighting, caustic effects", "fire and embers", "lens flare, anamorphic",
    "bokeh, shallow depth of field", "highly detailed background", "simple background, clean",
    "fog, mist, atmospheric", "rain, wet surface", "snow, winter scene",
    "starry night sky", "aurora borealis", "reflections, reflective surface",
    "dynamic angle, action shot", "fisheye lens", "vignette, dark corners",
    "color grading, cinematic tones", "film grain, noisy", "light leaks, vintage effect",
    "chromatic aberration", "bloom, soft glow", "particle effects, dust motes",
    "sun rays, crepuscular rays", "glowing eyes", "smoke, atmospheric"
]

ASPECT_CHOICES = ["1:1", "4:3", "3:4", "9:16", "16:9"]
BASE_CHOICES = [512, 640, 768, 896, 1024]
STEPS_CHOICES = list(range(4, 51))
CFG_CHOICES = [i * 0.5 for i in range(2, 25)]

from utils.common import ratio_to_dims

def load_user_settings(user_id: int) -> dict:
    fp = USER_DATA_DIR / f"{user_id}.json"
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_user_settings(user_id: int, settings: dict) -> None:
    fp = USER_DATA_DIR / f"{user_id}.json"
    fp.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")

def lora_tokens(settings: dict) -> str:
    lst = settings.get("loras", [])
    if not lst:
        return ""
    return " ".join([f"<lora:{name}:1>" for name in lst])

def compose_prompt(user_settings: dict, user_prompt: str) -> str:
    """Enhanced prompt composition with modifiers and loras."""
    
    pre_modifiers = ", ".join(user_settings.get("pre_modifiers", []))
    post_modifiers = ", ".join(user_settings.get("post_modifiers", []))
    
    parts = [
        pre_modifiers,
        user_prompt,
        post_modifiers,
        lora_tokens(user_settings)
    ]
    
    final_prompt = ", ".join(filter(None, parts))
    logging.info(f"Composed prompt: {final_prompt[:150]}...")
    return final_prompt



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(format_welcome_message(), parse_mode="HTML")

async def txt2img(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    settings = load_user_settings(user_id)

    # Validate and clean selected LoRAs
    try:
        available_loras = await fetch_loras()
        user_loras = settings.get("loras", [])
        valid_loras = [lora for lora in user_loras if lora in available_loras]
        
        if len(valid_loras) < len(user_loras):
            settings["loras"] = valid_loras
            save_user_settings(user_id, settings)
            logging.info(f"Removed invalid LoRAs for user {user_id}. Kept: {valid_loras}")

    except Exception as e:
        logging.error(f"Failed to fetch or validate LoRAs: {e}")

    prompt_raw = " ".join(context.args).strip() if getattr(context, "args", None) else (update.message.text if update.message else "")
    # Parse resource keywords (f_anime, r_color, etc.) before composing final prompt
    prompt_parsed = prompt_generator.generate(prompt_raw)
    prompt = compose_prompt(settings, prompt_parsed)
    if not prompt:
        await update.message.reply_text(
            f"{FormatText.bold(FormatText.emoji('❌ Uso incorrecto', '⚠️'))}\n"
            f"Por favor usa: {FormatText.code('/txt2img <tu prompt>')}\n\n"
            f"Ejemplo: {FormatText.code('/txt2img a beautiful landscape with mountains')}",
            parse_mode="HTML"
        )
        return
    try:
        n_images = int(settings.get("n_iter", 1))
        # Enhanced queue message with emojis and better formatting
        queue_message = (
            f"{FormatText.bold(FormatText.emoji('🎨 Solicitud recibida', '✅'))}\n"
            f"{FormatText.bold('Prompt:')} {FormatText.code(prompt[:100] + '...' if len(prompt) > 100 else prompt)}\n"
            f"{FormatText.bold('Imágenes:')} {FormatText.code(str(n_images))}\n"
            f"{FormatText.bold('Estado:')} {FormatText.emoji('En cola', '⏳')}\n\n"
            f"{FormatText.italic('Te notificaré cuando esté listo...')}"
        )
        
        status_message = await update.message.reply_text(queue_message, parse_mode="HTML")
        await JOBQ.enqueue(GenJob(user_id=user_id, chat_id=update.effective_chat.id, prompt=prompt, status_message_id=status_message.message_id, user_name=update.effective_user.first_name, operation_type="txt2img"))
    except Exception as e:
        error_msg = format_error_message(str(e))
        err_msg = await update.message.reply_text(
            error_msg,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cerrar", callback_data="err:close")]])
        )
        async def _auto_delete():
            try:
                await asyncio.sleep(10)
                await context.bot.delete_message(chat_id=err_msg.chat_id, message_id=err_msg.message_id)
            except Exception:
                pass
        asyncio.create_task(_auto_delete())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.chat_data.get("edit_target"):
        text = (update.message.text or "").strip()
        if text.lower() in {"/cancel", "cancel"}:
            context.chat_data.clear()
            await update.message.reply_text("Edición cancelada.")
            return
        context.chat_data["edit_candidate"] = text
        target = context.chat_data.get("edit_target")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Guardar", callback_data=f"edit:confirm:{target}"), InlineKeyboardButton("Cancelar", callback_data="edit:cancel")]])
        await update.message.reply_text(f"Confirmar {target}_value:\n{text}", reply_markup=kb)
        return
    context.args = [update.message.text]
    await txt2img(update, context)

def settings_summary(s: dict, model_name: str = None) -> str:
    w, h = ratio_to_dims(s.get("aspect_ratio", "1:1"), s.get("base_size", 512))
    pre_count = len(s.get("pre_modifiers", []))
    post_count = len(s.get("post_modifiers", []))
    lcount = len(s.get("loras", []))
    
    # Check for preset prompts
    preset_pre = s.get("preset_pre_prompt", "")
    preset_post = s.get("preset_post_prompt", "")
    preset_neg = s.get("preset_negative_prompt", "")
    
    summary = (
        f"🖼️ Modelo: {model_name or 'Desconocido'}\n"
        f"🎨 Sampler: {s.get('sampler_name')}\n"
        f"⏰ Scheduler: {s.get('scheduler') or '-'}\n"
        f"⚡ Steps: {s.get('steps')}\n"
        f"🎛️ CFG: {s.get('cfg_scale')}\n"
        f"📐 Aspect: {s.get('aspect_ratio')} ({w}x{h})\n"
        f"📏 Base: {s.get('base_size')}\n"
        f"🔢 Imagenes: {s.get('n_iter')}\n"
        f"🎲 Pre: {pre_count} activados\n"
        f"✨ Post: {post_count} activados\n"
        f"🎭 Loras: {lcount}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📦 Preset Prompts:\n"
        f"  • Pre: {'✅' if preset_pre else '❌'}\n"
        f"  • Post: {'✅' if preset_post else '❌'}\n"
        f"  • Negative: {'✅' if preset_neg else '❌'}"
    )
    return summary

def _truncate(text: str, limit: int = 60) -> str:
    return text if len(text) <= limit else text[:limit] + "…"

def are_settings_compliant(settings: dict, preset: Preset) -> bool:
    # Si no hay preset (sin conexión a A1111), no podemos validar
    if preset is None:
        return False
    if settings.get("steps") not in preset.steps:
        return False
    if settings.get("cfg_scale") not in preset.cfg:
        return False
    if settings.get("sampler_name") not in preset.samplers:
        return False
    if settings.get("scheduler") not in preset.schedulers:
        return False
    if settings.get("base_size") not in preset.resolutions:
        return False
    return True

def _tip_for_set(key: str, s: dict) -> str:
    if key == "aspect" or key == "base":
        w, h = ratio_to_dims(s.get("aspect_ratio", "1:1"), s.get("base_size", 512))
        return f"Aspect {s.get('aspect_ratio')} → {w}x{h}"
    if key == "steps":
        return f"Steps {s.get('steps')}"
    if key == "cfg":
        return f"CFG {s.get('cfg_scale')}"
    if key == "sampler":
        return f"Sampler {s.get('sampler_name')}"
    if key == "scheduler":
        return f"Scheduler {s.get('scheduler') or 'none'}"
    if key == "niter":
        return f"Images {s.get('n_iter')}"
    return "Guardado"



async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    
    s = load_user_settings(user_id)
    try:
        model_name = await get_current_model()
        preset = get_preset_for_model(model_name)
    except Exception as e:
        logging.warning(f"A1111 offline: {e}")
        model_name = None
        preset = None
    is_compliant = are_settings_compliant(s, preset)

    if chat_type != "private":
        # Try to send to DM
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=settings_summary(s, model_name),
                reply_markup=main_menu_keyboard(s, is_compliant),
                parse_mode="HTML"
            )
            
            # Notify in group and auto-delete
            msg = await update.message.reply_text(f"⚙️ {update.effective_user.first_name}, te envié la configuración por privado. 📩")
            
            async def _del():
                await asyncio.sleep(5)
                try:
                    await msg.delete()
                    await update.message.delete()
                except Exception:
                    pass
            asyncio.create_task(_del())
            
        except Exception as e:
            logging.warning(f"Could not send settings to DM for {user_id}: {e}")
            await update.message.reply_text(
                f"❌ {update.effective_user.first_name}, no pude enviarte el mensaje privado. Por favor inicia el bot en privado primero."
            )
        return

    await update.message.reply_text(settings_summary(s, model_name), reply_markup=main_menu_keyboard(s, is_compliant), parse_mode="HTML")








async def settings_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    data = q.data
    user_id = update.effective_user.id

    # Obtener el preset para el modelo actual
    model_name = await get_current_model()
    preset = get_preset_for_model(model_name)

    submenu_texts = {
        "aspect": "📐 Elige la proporción de la imagen (ancho:alto).",
        "base": "📏 Define el tamaño base de la imagen. Tamaños más grandes pueden tardar más en generarse.",
        "steps": "⚡️ Ajusta el número de pasos de generación. Más pasos pueden mejorar la calidad, pero tardan más.",
        "cfg": "🎛️ Controla qué tan estrictamente se sigue el prompt. Valores más altos son más estrictos.",
        "sampler": "🎨 Elige el método de muestreo. Cada uno produce un estilo de imagen diferente.",
        "scheduler": "⏰ Selecciona el programador de pasos. Afecta cómo se distribuyen los pasos de generación.",
        "niter": "🔢 Define cuántas imágenes generar a la vez.",
        "pre": "🎲 Elige un estilo predefinido para aplicar antes de tu prompt.",
        "post": "✨ Elige un estilo predefinido para aplicar después de tu prompt.",
        "loras": "🎭 Administra tus Loras (modelos mágicos que modifican el estilo). ✨",
        "model": "🖼️ Selecciona el checkpoint para tus generaciones. El modelo se aplicará automáticamente antes de generar imágenes.",
        "adetailer": "🎭 Modelos ADetailer disponibles (selecciona para upscale):",
    }
    
    # Log detallado del callback
    log_payload = {
        "timestamp": asyncio.get_event_loop().time(),
        "user_id": user_id,
        "callback_data": data,
        "message_id": q.message.message_id if q.message else None,
        "chat_id": update.effective_chat.id if update.effective_chat else None,
        "message_text": q.message.text if q.message and q.message.text else None,
        "message_caption": q.message.caption if q.message and q.message.caption else None,
        "has_document": bool(q.message.document) if q.message else False,
        "document_file_id": q.message.document.file_id if q.message and q.message.document else None
    }
    log_callback_payload(log_payload)
    logging.info(f"Callback recibido: user_id={user_id}, data={data}")
    
    s = load_user_settings(user_id)
    if data.startswith("err:close"):
        try:
            await q.message.delete()
        except Exception:
            pass
        await q.answer("Cerrado")
        return

    if data.startswith("mod:"):
        parts = data.split(":")
        kind = parts[1]
        action = parts[2]
        page = 0

        if action == "toggle":
            # Format: mod:kind:toggle:name:page
            payload = parts[3]
            page = int(parts[4])
            
            current_mods = s.get(f"{kind}_modifiers", [])
            if payload in current_mods:
                current_mods.remove(payload)
            else:
                current_mods.append(payload)
            s[f"{kind}_modifiers"] = current_mods
            save_user_settings(user_id, s)

        elif action == "page":
            # Format: mod:kind:page:page
            page = int(parts[3])
        
        modifier_list = PRE_MODIFIERS if kind == "pre" else POST_MODIFIERS
        selected_mods = s.get(f"{kind}_modifiers", [])
        kb = modifiers_page_keyboard(kind, modifier_list, set(selected_mods), page)
        
        # Build the text with current modifiers
        current_mods_text = ", ".join(selected_mods) if selected_mods else "Ninguno"
        text = submenu_texts[kind] + f"\n\n<b>Actual:</b> {current_mods_text}"
        
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        await q.answer()
        return

    if data.startswith("menu:"):
        parts = data.split(":")
        kind = parts[1]
        if kind == "autoconfig":
            # Check if we have a valid preset
            if preset is None:
                logging.warning(f"AutoConfig failed: model_name='{model_name}', preset is None")
                await q.answer("⚠️ No se pudo detectar el modelo actual o no hay preset disponible", show_alert=True)
                return
            
            s["steps"] = random.choice(preset.steps)
            s["cfg_scale"] = random.choice(preset.cfg)
            s["sampler_name"] = random.choice(preset.samplers)
            s["scheduler"] = random.choice(preset.schedulers)
            
            base_size = random.choice(preset.resolutions)
            s["base_size"] = base_size
            
            # For aspect ratio, let's try to find a suitable one or default to 1:1
            if base_size in [512, 768, 1024]:
                s["aspect_ratio"] = "1:1"
            else:
                # A simple logic to find a suitable aspect ratio, can be improved
                s["aspect_ratio"] = random.choice(["1:1", "4:3", "3:4", "16:9", "9:16"])
            
            # Save preset prompts
            s["preset_pre_prompt"] = preset.pre_prompt
            s["preset_post_prompt"] = preset.post_prompt
            s["preset_negative_prompt"] = preset.negative_prompt

            save_user_settings(user_id, s)
            
            await q.answer("✅ Configuración automática aplicada")
            
            # Update the message with new settings
            text = settings_summary(s, model_name)
            # After autoconfig, settings are compliant
            kb = main_menu_keyboard(s, is_compliant=True)
            await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            return
        if kind == "main":
            is_compliant = are_settings_compliant(s, preset)
            await q.edit_message_text(settings_summary(s, model_name), reply_markup=main_menu_keyboard(s, is_compliant))
            await q.answer()
            return

        if kind == "close":
            try:
                await q.message.delete()
            except Exception:
                pass
            await q.answer("Cerrado")
            return

        if kind in submenu_texts:
            text = submenu_texts[kind]
            kb = None
            if kind == "sampler":
                try:
                    samplers = await fetch_samplers()
                    recommended = [r.lower() for r in (preset.samplers if preset else [])]
                    rows = [[InlineKeyboardButton(f"{v} {'👌' if v.lower() in recommended else ''}".strip(), callback_data=f"set:sampler:{v}")] for v in samplers]
                    rows.append([InlineKeyboardButton("Volver", callback_data="menu:main"), InlineKeyboardButton("Cerrar", callback_data="menu:close")])
                    kb = InlineKeyboardMarkup(rows)
                except Exception as e:
                    text = f"Error: {e}"
                    kb = main_menu_keyboard(s, are_settings_compliant(s, preset))
            elif kind == "scheduler":
                sched = await fetch_schedulers()
                items = sched or [{"name": "none", "label": "none"}]
                recommended = [r.lower() for r in (preset.schedulers if preset else [])]
                rows = [[InlineKeyboardButton(f"{it['label']} {'👌' if it['name'].lower() in recommended else ''}".strip(), callback_data=f"set:scheduler:{it['name']}")] for it in items]
                rows.append([InlineKeyboardButton("Volver", callback_data="menu:main"), InlineKeyboardButton("Cerrar", callback_data="menu:close")])
                kb = InlineKeyboardMarkup(rows)
            elif kind == "loras":
                page = int(parts[2]) if len(parts) > 2 else 0
                names = await fetch_loras()
                kb = loras_page_keyboard(names, set(s.get("loras", [])), page)
            elif kind == "model":
                page = int(parts[2]) if len(parts) > 2 else 0
                from ui.menus import models_page_keyboard
                models = await fetch_sd_models()
                current_user_model = s.get("selected_model")
                kb = models_page_keyboard(models, current_user_model or "", page)
                text = submenu_texts["model"]
                if current_user_model:
                    text += f"\n\n<b>Actual:</b> {current_user_model}"
                await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
                await q.answer()
                return
            elif kind == "pre" or kind == "post":
                page = int(parts[2]) if len(parts) > 2 else 0
                modifier_list = PRE_MODIFIERS if kind == "pre" else POST_MODIFIERS
                selected_mods = s.get(f"{kind}_modifiers", [])
                kb = modifiers_page_keyboard(kind, modifier_list, set(selected_mods), page)
                
                # Build the text with current modifiers
                current_mods_text = ", ".join(selected_mods) if selected_mods else "Ninguno"
                text = submenu_texts[kind] + f"\n\n<b>Actual:</b> {current_mods_text}"
                await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
                await q.answer()
                return
            elif kind == "adetailer":
                page = int(parts[2]) if len(parts) > 2 else 0
                models = await fetch_adetailer_models()
                selected_order = s.get("adetailer_models", [])
                kb = adetailer_page_keyboard(models, selected_order, page)
            else:
                kb = submenu_keyboard_static(kind, preset)
            
            await q.edit_message_text(text, reply_markup=kb)
            await q.answer()
            return
    if data.startswith("set:"):
        _, key, val = data.split(":", 2)
        if key == "aspect":
            s["aspect_ratio"] = val
        elif key == "base":
            s["base_size"] = int(val)
        elif key == "steps":
            s["steps"] = int(val)
        elif key == "cfg":
            s["cfg_scale"] = float(val)
        elif key == "sampler":
            s["sampler_name"] = val
        elif key == "scheduler":
            s["scheduler"] = "" if val == "none" else val
        elif key == "niter":
            s["n_iter"] = int(val)
        elif key == "model":
            # Guardar el modelo seleccionado
            s["selected_model"] = val
            save_user_settings(user_id, s)
            
            # Aplicar Auto Config con el preset del modelo seleccionado
            model_preset = get_preset_for_model(val)
            
            if model_preset:
                # Aplicar configuración automática según el preset
                s["steps"] = random.choice(model_preset.steps)
                s["cfg_scale"] = random.choice(model_preset.cfg)
                s["sampler_name"] = random.choice(model_preset.samplers)
                s["scheduler"] = random.choice(model_preset.schedulers)
                base_size = random.choice(model_preset.resolutions)
                s["base_size"] = base_size
                
                if base_size in [512, 768, 1024]:
                    s["aspect_ratio"] = "1:1"
                else:
                    s["aspect_ratio"] = random.choice(["1:1", "4:3", "3:4", "16:9", "9:16"])
                
                # Guardar preset prompts
                s["preset_pre_prompt"] = model_preset.pre_prompt
                s["preset_post_prompt"] = model_preset.post_prompt
                s["preset_negative_prompt"] = model_preset.negative_prompt
                
                save_user_settings(user_id, s)
                
                # Update message and show Auto Config was applied
                is_compliant = are_settings_compliant(s, model_preset)
                await q.edit_message_text(settings_summary(s, val), reply_markup=main_menu_keyboard(s, is_compliant))
                await q.answer(f"✅ Modelo cambiado a {val} y Auto Config aplicado")
                return
            else:
                save_user_settings(user_id, s)
                is_compliant = are_settings_compliant(s, preset)
                await q.edit_message_text(settings_summary(s, val), reply_markup=main_menu_keyboard(s, is_compliant))
                await q.answer(f"✅ Modelo cambiado a {val}")
                return
        elif key == "pre":
            s["pre_mode"] = val
            if val == "none":
                s["pre_value"] = ""
        elif key == "post":
            s["post_mode"] = val
            if val == "none":
                s["post_value"] = ""
        save_user_settings(user_id, s)
        is_compliant = are_settings_compliant(s, preset)
        await q.edit_message_text(settings_summary(s, model_name), reply_markup=main_menu_keyboard(s, is_compliant))
        
        # Enhanced settings update message with emojis
        setting_emoji = {
            "aspect": "📐",
            "base": "📏",
            "steps": "⚡",
            "cfg": "🎛️",
            "sampler": "🎨",
            "scheduler": "⏰",
            "niter": "🔢",
        }.get(key, "⚙️")
        
        value_display = val
        if key in ["aspect", "base", "steps", "niter"]:
            value_display = val
        elif key == "cfg":
            value_display = f"{float(val):.1f}"
        
        await q.answer(f"{setting_emoji} {_tip_for_set(key, s)}")
        return
    if data.startswith("loras:"):
        parts = data.split(":")
        action = parts[1]
        if action == "toggle":
            name = parts[2]
            page = int(parts[3]) if len(parts) > 3 else 0
            cur_before = set(s.get("loras", []))
            added = name not in cur_before
            cur = set(cur_before)
            if not added:
                cur.remove(name)
            else:
                cur.add(name)
            s["loras"] = sorted(cur)
            save_user_settings(user_id, s)
            names = await fetch_loras()
            kb = loras_page_keyboard(names, cur, page)
            await q.edit_message_text(submenu_texts["loras"], reply_markup=kb)
            await q.answer(("Lora + " if added else "Lora - ") + _truncate(name) + f" (total {len(cur)})")
            return
        if action == "page":
            page = int(parts[2])
            names = await fetch_loras()
            kb = loras_page_keyboard(names, set(s.get("loras", [])), page)
            await q.edit_message_text(submenu_texts["loras"], reply_markup=kb)
            await q.answer()
            return

    if data.startswith("adetailer:"):
        parts = data.split(":")
        action = parts[1]
        if action == "toggle":
            name = parts[2]
            page = int(parts[3]) if len(parts) > 3 else 0
            
            # Use list to preserve selection order
            current_list = s.get("adetailer_models", [])
            # Ensure it's a list (backward compatibility)
            if not isinstance(current_list, list):
                current_list = list(current_list)
            
            if name in current_list:
                current_list.remove(name)
                added = False
            else:
                current_list.append(name)
                added = True
            
            s["adetailer_models"] = current_list
            save_user_settings(user_id, s)
            
            models = await fetch_adetailer_models()
            kb = adetailer_page_keyboard(models, current_list, page)
            await q.edit_message_text(submenu_texts["adetailer"], reply_markup=kb)
            await q.answer(("ADetailer + " if added else "ADetailer - ") + _truncate(name) + f" (total {len(current_list)})")
            return
        if action == "page":
            page = int(parts[2])
            models = await fetch_adetailer_models()
            kb = adetailer_page_keyboard(models, s.get("adetailer_models", []), page)
            await q.edit_message_text(submenu_texts["adetailer"], reply_markup=kb)
            await q.answer()
            return

    if data.startswith("img:") or data.startswith("job:"):
        parts = data.split(":")
        action = parts[1]
        
        logging.info(f"=== CALLBACK RECIBIDO ===")
        logging.info(f"Procesando callback imagen/job: data={data}, action={action}, parts={parts}")
        logging.info(f"User ID: {user_id}, Message ID: {q.message.message_id if q.message else 'N/A'}")
        
        # Intentar obtener el trabajo usando get_job() primero
        job_data = None
        if data.startswith("job:") and len(parts) > 2:
            try:
                message_id = int(parts[2])
                job_data = get_job(message_id)
                logging.info(f"Buscando job con message_id={message_id}, encontrado={job_data is not None}")
                if job_data:
                    logging.info(f"Job data encontrado: {json.dumps(job_data, ensure_ascii=False)}")
            except (ValueError, IndexError) as e:
                logging.error(f"Error al parsear message_id del callback job: {e}")
        elif data.startswith("img:") and len(parts) >= 4:
            # Formato antiguo img:action:timestamp:request_id - usar regex fallback
            logging.info(f"Callback formato antiguo img:, usando regex fallback")
        else:
            logging.info(f"Callback no es job: o no tiene suficientes partes. data={data}")
        
        # Inicializar variables con valores por defecto
        prompt_p = ""
        steps_p = 20
        sampler_p = "Euler"
        sched_p = "normal"
        cfg_p = 7.0
        seed_p = -1
        width_p = 512
        height_p = 512
        
        if job_data:
            # Usar datos del trabajo almacenado
            prompt_p = job_data.get("prompt", "")
            steps_p = job_data.get("steps", 20)
            sampler_p = job_data.get("sampler_name", "Euler")
            sched_p = job_data.get("scheduler", "normal")
            cfg_p = job_data.get("cfg_scale", 7.0)
            seed_p = job_data.get("seed", -1)
            width_p = job_data.get("width", 512)
            height_p = job_data.get("height", 512)
            logging.info(f"Usando job_data: prompt='{prompt_p[:50]}...', steps={steps_p}, sampler={sampler_p}, cfg={cfg_p}, seed={seed_p}, size={width_p}x{height_p}")
        else:
            # Fallback al regex para compatibilidad con mensajes antiguos
            cap = q.message.caption or ""
            logging.info(f"Usando fallback regex. Caption: {cap[:200]}...")
            
            # Regex mucho más robusto para parsear captions
            # Formato esperado:
            # ✅ 🎨 Generación completada
            # 
            # 📝 Prompt: [prompt aquí, puede tener múltiples líneas]
            # 
            # ⚙️ Configuración:
            # • Pasos: [número]
            # • Sampler: [sampler]
            # • Scheduler: [scheduler]
            # • CFG: [número]
            # • Seed: [número]
            # • Tamaño: [ancho]x[alto]
            
            # Primero intentar con un regex más específico
            m = re.search(
                r"📝\s*Prompt:\s*([\s\S]*?)\n\s*⚙️\s*Configuración:\s*\n"
                r"\s*•\s*Pasos:\s*(\d+)\s*\n"
                r"\s*•\s*Sampler:\s*(.*?)\s*\n"
                r"\s*•\s*Scheduler:\s*(.*?)\s*\n"
                r"\s*•\s*CFG:\s*([\d\.]+)\s*\n"
                r"\s*•\s*Seed:\s*(\-?\d+)\s*\n"
                r"\s*•\s*Tamaño:\s*(\d+)x(\d+)",
                cap
            )
            
            if not m:
                # Fallback: intentar con formato más flexible
                logging.info("Primer regex falló, intentando regex más flexible...")
                m = re.search(
                    r"Prompt:\s*([\s\S]*?)\n.*?(?:Configuración|Configuration):.*?"
                    r"Pasos:\s*(\d+).*?"
                    r"Sampler:\s*(.*?).*?"
                    r"Scheduler:\s*(.*?).*?"
                    r"CFG:\s*([\d\.]+).*?"
                    r"Seed:\s*(\-?\d+).*?"
                    r"Tamaño:\s*(\d+)x(\d+)",
                    cap,
                    re.IGNORECASE | re.DOTALL
                )
            
            if not m:
                # Último fallback: buscar cada campo individualmente
                logging.info("Segundo regex falló, intentando parseo individual...")
                
                prompt_match = re.search(r"📝\s*Prompt:\s*([\s\S]*?)(?=\n\s*⚙️|\n\s*Configuración|\n\s*Configuration|$)", cap)
                steps_match = re.search(r"Pasos:\s*(\d+)", cap, re.IGNORECASE)
                sampler_match = re.search(r"Sampler:\s*(.*?)(?=\n|\s*•|$)", cap, re.IGNORECASE)
                scheduler_match = re.search(r"Scheduler:\s*(.*?)(?=\n|\s*•|$)", cap, re.IGNORECASE)
                cfg_match = re.search(r"CFG:\s*([\d\.]+)", cap, re.IGNORECASE)
                seed_match = re.search(r"Seed:\s*(\-?\d+)", cap, re.IGNORECASE)
                size_match = re.search(r"Tamaño:\s*(\d+)x(\d+)", cap, re.IGNORECASE)
                
                if prompt_match and steps_match and sampler_match and scheduler_match and cfg_match and seed_match and size_match:
                    prompt_p = prompt_match.group(1).strip()
                    steps_p = int(steps_match.group(1))
                    sampler_p = sampler_match.group(1).strip()
                    sched_p = scheduler_match.group(1).strip()
                    cfg_p = float(cfg_match.group(1))
                    seed_p = int(seed_match.group(1))
                    width_p = int(size_match.group(1))
                    height_p = int(size_match.group(2))
                    logging.info(f"Parseo individual exitoso: prompt='{prompt_p[:50]}...', steps={steps_p}, sampler={sampler_p}, cfg={cfg_p}, seed={seed_p}, size={width_p}x{height_p}")
                else:
                    logging.warning(f"Todos los regex fallaron. Caption completo: {cap}")
                    await q.answer("Expirado")
                    return
            else:
                prompt_p = m.group(1).strip()
                steps_p = int(m.group(2))
                sampler_p = m.group(3).strip()
                sched_p = m.group(4).strip()
                cfg_p = float(m.group(5))
                seed_p = int(m.group(6))
                width_p = int(m.group(7))
                height_p = int(m.group(8))
                logging.info(f"Regex exitoso: prompt='{prompt_p[:50]}...', steps={steps_p}, sampler={sampler_p}, cfg={cfg_p}, seed={seed_p}, size={width_p}x{height_p}")
        logging.info(f"Procesando acción: {action} con prompt='{prompt_p[:50]}...', steps={steps_p}, sampler={sampler_p}, cfg={cfg_p}, seed={seed_p}, size={width_p}x{height_p}")
        
        if action == "repeat":
            logging.info(f"Ejecutando REPEAT con seed aleatorio y auto-config parcial")
            
            # Get current model preset to auto-configure sampler/scheduler
            try:
                current_model_name = await get_current_model()
                current_preset = get_preset_for_model(current_model_name)
            except Exception as e:
                logging.warning(f"Could not get model/preset for repeat auto-config: {e}")
                current_preset = None

            new_sampler = sampler_p
            new_scheduler = sched_p
            
            if current_preset:
                new_sampler = random.choice(current_preset.samplers)
                new_scheduler = random.choice(current_preset.schedulers)
                logging.info(f"Repeat Auto-Config: Sampler={new_sampler}, Scheduler={new_scheduler}")

            overrides = {
                "steps": steps_p,
                "cfg_scale": cfg_p,
                "sampler_name": new_sampler,
                "scheduler": new_scheduler,
                "width": width_p,
                "height": height_p,
                "seed": -1,
                "n_iter": int(load_user_settings(user_id).get("n_iter", 1)),
            }
            logging.info(f"repeat action overrides: {overrides}")
            # Enhanced repeat message
            repeat_message = (
                f"{FormatText.bold(FormatText.emoji('🔄 Iniciando repetición', '✅'))}\n"
                f"{FormatText.bold('Prompt:')} {FormatText.code(prompt_p[:100] + '...' if len(prompt_p) > 100 else prompt_p)}\n"
                f"{FormatText.bold('Imágenes:')} {FormatText.code(str(overrides['n_iter']))}\n"
                f"{FormatText.bold('Seed:')} {FormatText.code('Nuevo aleatorio')}\n\n"
                f"{FormatText.italic('Generando con configuración idéntica pero seed diferente...')}"
            )
            status_message = await update.effective_chat.send_message(repeat_message, parse_mode="HTML")
            await JOBQ.enqueue(GenJob(user_id=user_id, chat_id=update.effective_chat.id, prompt=prompt_p, overrides=overrides, status_message_id=status_message.message_id, user_name=update.effective_user.first_name, operation_type="repeat"))
            return
        if action == "upscale":
            logging.info(f"Ejecutando UPSCALE con HR")
            overrides = {
                "steps": steps_p,
                "cfg_scale": cfg_p,
                "sampler_name": sampler_p,
                "scheduler": sched_p,
                "width": width_p,
                "height": height_p,
                "seed": seed_p,
                "n_iter": 1,
            }
            hr = {
                "hr_scale": 1.5,
                "hr_second_pass_steps": max(1, int(overrides.get("steps", 4)) // 2),
                "hr_upscaler": "R-ESRGAN 4x+",
                "denoising_strength": 0.3,
                "hr_sampler_name": sampler_p,
                "hr_scheduler": sched_p,
            }
            hr = {
                "hr_scale": 1.5,
                "hr_second_pass_steps": max(1, int(overrides.get("steps", 4)) // 2),
                "hr_upscaler": "R-ESRGAN 4x+",
                "denoising_strength": 0.3,
                "hr_sampler_name": sampler_p,
                "hr_scheduler": sched_p,
            }
            
            # Load user's selected ADetailer models
            user_settings = load_user_settings(user_id)
            selected_ad_models = user_settings.get("adetailer_models", [])
            
            always_scripts = {}
            if selected_ad_models:
                ad_args = [{"ad_model": m, "ad_confidence": 0.3} for m in selected_ad_models]
                always_scripts["ADetailer"] = {"args": ad_args}
                logging.info(f"Upscale using ADetailer models: {selected_ad_models}")
            else:
                try:

                    available = await fetch_adetailer_models()
                    defaults = ["face_yolov8n.pt", "mediapipe_face_mesh_eyes_only"]
                    auto_models = [m for m in defaults if m in available]
                    if auto_models:
                        ad_args = [{"ad_model": m, "ad_confidence": 0.3} for m in auto_models]
                        always_scripts["ADetailer"] = {"args": ad_args}
                        logging.info(f"Upscale using default ADetailer models: {auto_models}")
                    else:
                        logging.info("Upscale without ADetailer defaults (not available)")
                except Exception as e:
                    logging.warning(f"Failed to load default ADetailer models: {e}")

            logging.info(f"upscale action overrides: {overrides}, hr: {hr}")
            # Enhanced upscale message
            upscale_message = (
                f"{FormatText.bold(FormatText.emoji('🔍 Upscale HR encolado', '✅'))}\n"
                f"{FormatText.bold('Prompt:')} {FormatText.code(prompt_p[:100] + '...' if len(prompt_p) > 100 else prompt_p)}\n"
                f"{FormatText.bold('Factor:')} {FormatText.code('1.5x')}\n"
                f"{FormatText.bold('Upscaler:')} {FormatText.code('R-ESRGAN 4x+')}\n"
                f"{FormatText.bold('Denoising:')} {FormatText.code('0.3')}\n"
                f"{FormatText.bold('ADetailer:')} {FormatText.code(str(len(selected_ad_models)) + ' modelos') if selected_ad_models else 'Desactivado'}\n\n"
                f"{FormatText.italic('Generando versión de alta resolución...')}"
            )
            status_message = await update.effective_chat.send_message(upscale_message, parse_mode="HTML")
            await JOBQ.enqueue(GenJob(user_id=user_id, chat_id=update.effective_chat.id, prompt=prompt_p, overrides=overrides, hr_options=hr, alwayson_scripts=always_scripts, status_message_id=status_message.message_id, user_name=update.effective_user.first_name, operation_type="upscale_hr", operation_metadata={"hr_scale": 1.5, "upscaler": "R-ESRGAN 4x+", "denoising": 0.3}))
            return
        if action == "newseed":
            logging.info(f"Ejecutando NEWSEED con seed aleatorio")
            # Generate with new random seed but same settings
            overrides = {
                "steps": steps_p,
                "cfg_scale": cfg_p,
                "sampler_name": sampler_p,
                "scheduler": sched_p,
                "width": width_p,
                "height": height_p,
                "seed": -1,  # Random seed
                "n_iter": int(load_user_settings(user_id).get("n_iter", 1)),
            }
            logging.info(f"newseed action overrides: {overrides}")
            # Enhanced message with emojis
            seed_message = (
                f"{FormatText.bold(FormatText.emoji('🎲 Nueva generación con seed aleatorio', '✨'))}\n"
                f"{FormatText.bold('Prompt:')} {FormatText.code(prompt_p[:100] + '...' if len(prompt_p) > 100 else prompt_p)}\n"
                f"{FormatText.bold('Imágenes:')} {FormatText.code(str(overrides['n_iter']))}\n"
                f"{FormatText.italic('Se usará un seed diferente para variar el resultado...')}"
            )
            status_message = await update.effective_chat.send_message(seed_message, parse_mode="HTML")
            await JOBQ.enqueue(GenJob(user_id=user_id, chat_id=update.effective_chat.id, prompt=prompt_p, overrides=overrides, status_message_id=status_message.message_id, user_name=update.effective_user.first_name, operation_type="newseed"))
            await q.answer("Nuevo seed en cola")
            return

        if action == "final":
            logging.info(f"=== INICIANDO FINAL UPSCALE ===")
            logging.info(f"Ejecutando FINAL UPSCALE - data={data}, user_id={user_id}")
            
            try:
                # Responder inmediatamente para evitar timeout
                await q.answer("⏳ Iniciando upscale final... esto puede tardar unos segundos.")
                
                # Test connection to A1111 API first
                from services.a1111 import a1111_test_connection
                connection_ok = await a1111_test_connection()
                if not connection_ok:
                    logging.error("No se pudo conectar a la API de A1111")
                    await update.effective_chat.send_message("❌ Error: No se pudo conectar a A1111")
                    return
                
                logging.info("Conexión a A1111 exitosa, procediendo con FINAL UPSCALE")
                    
                # Si tenemos job_data con file_id, usarlo directamente
                if job_data and 'file_id' in job_data:
                    file_id = job_data['file_id']
                    logging.info(f"Usando file_id del job_data: {file_id}")
                    file = await context.bot.get_file(file_id)
                else:
                    # Fallback al documento del mensaje actual
                    doc = q.message.document
                    if not doc:
                        logging.warning(f"No hay documento en el mensaje actual para final upscale")
                        await update.effective_chat.send_message("❌ Error: No se encontró la imagen original.")
                        return
                    logging.info(f"Usando documento del mensaje actual: {doc.file_id}")
                    file = await context.bot.get_file(doc.file_id)
                
                logging.info(f"Descargando imagen de Telegram: file_path={file.file_path}")

                img_bytes = None
                try:
                    # Determinar la URL de descarga correcta
                    if file.file_path.startswith('http'):
                        url = file.file_path
                    else:
                        url = f"https://api.telegram.org/file/bot{BOT_TOKEN_DEFAULT}/{file.file_path}"
                    
                    logging.info(f"URL de descarga final: {url}")

                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as resp:
                            resp.raise_for_status()
                            # LEER LA IMAGEN DENTRO DEL CONTEXTO de la sesión
                            img_bytes = await resp.read()
                    
                    if not img_bytes:
                        raise ValueError("La imagen descargada está vacía.")

                    logging.info(f"Imagen descargada: {len(img_bytes)} bytes")
                    
                    # Log Base64 string for debugging
                    base64_encoded = base64.b64encode(img_bytes).decode('utf-8')
                    with open(LOG_DIR / "base64_debug.log", "w") as f:
                        f.write(base64_encoded)
                    logging.info("Base64 de la imagen guardado en base64_debug.log")
                        
                except Exception as e:
                    logging.error(f"Error al descargar o procesar la imagen: {e}", exc_info=True)
                    await update.effective_chat.send_message("❌ Error al descargar la imagen para upscale.")
                    return
                
                logging.info(f"Llamando a a1111_extra_single_image con {len(img_bytes)} bytes")
                logging.info(f"Parámetros del upscale: upscaler_1='R-ESRGAN 4x+', upscaling_resize=2")
                
                # Verificar que los bytes de imagen sean válidos
                if not img_bytes or len(img_bytes) < 100:
                    logging.error(f"Imagen descargada inválida: {len(img_bytes)} bytes")
                    await update.effective_chat.send_message("❌ Error: imagen descargada inválida.")
                    return
                
                # Importar la función aquí para asegurar que esté disponible
                from services.a1111 import a1111_extra_single_image
                logging.info("Función a1111_extra_single_image importada correctamente")
                
                out = await a1111_extra_single_image(img_bytes, upscaler_1="R-ESRGAN 4x+", upscaling_resize=2)
                logging.info(f"Resultado del upscale: {len(out) if out else 0} bytes")
                
                if not out:
                    logging.error("Upscale resultó en imagen vacía")
                    await update.effective_chat.send_message("❌ Error: El upscale falló (imagen vacía).")
                    return
                    
                bio = BytesIO(out); bio.seek(0)
                
                # Enhanced final upscale message
                final_message = (
                    f"{FormatText.bold(FormatText.emoji('🔍 Final Upscale completado', '✅'))}\n"
                    f"{FormatText.bold('Upscaler:')} {FormatText.code('R-ESRGAN 4x+')}\n"
                    f"{FormatText.bold('Factor:')} {FormatText.code('2x')}\n\n"
                    f"{FormatText.italic('Imagen final lista para descargar...')}"
                )
                await update.effective_chat.send_document(InputFile(bio, filename="final_upscale.png"), caption=final_message, parse_mode="HTML")
                logging.info("=== FINAL UPSCALE COMPLETADO EXITOSAMENTE ===")
                return
                
            except Exception as e:
                logging.error(f"=== ERROR CRÍTICO EN FINAL UPSCALE ===", exc_info=True)
                logging.error(f"Exception type: {type(e).__name__}")
                logging.error(f"Exception message: {str(e)}")
                
                # Capturar información adicional del error
                error_details = f"{type(e).__name__}: {str(e)}"
                if "resp" in locals():
                    try:
                        error_text = await resp.text()
                        logging.error(f"Response error details: {error_text[:500]}")
                        error_details += f" | Response: {error_text[:200]}"
                    except Exception:
                        pass
                
                await update.effective_chat.send_message(f"❌ Error crítico en upscale: {error_details[:100]}")
                return

async def _post_init(app):
    await JOBQ.start(app.bot)

def build_app() -> "Application":
    token = BOT_TOKEN_DEFAULT
    app = ApplicationBuilder().token(token).post_init(_post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("txt2img", txt2img))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CallbackQueryHandler(settings_menu_cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app

async def cleanup_error_messages(app):
    """Clean up existing error messages from bot chat history on startup"""
    try:
        logging.info("🧹 Iniciando limpieza de mensajes de error...")
        
        from storage.error_messages import load_error_messages, clear_all_error_messages
        
        bot = app.bot
        error_msgs = load_error_messages()
        
        deleted_count = 0
        failed_count = 0
        
        # Iterate through all tracked error messages
        for chat_id, message_ids in error_msgs.items():
            for message_id in message_ids:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                    deleted_count += 1
                    logging.debug(f"Deleted error message {message_id} from chat {chat_id}")
                except Exception as e:
                    failed_count += 1
                    logging.debug(f"Failed to delete message {message_id} from chat {chat_id}: {e}")
        
        # Clear the tracking file after cleanup attempt
        clear_all_error_messages()
        
        if deleted_count > 0:
            logging.info(f"✅ Limpieza completada: {deleted_count} mensajes eliminados, {failed_count} fallidos")
        else:
            logging.info("✅ No hay mensajes de error para limpiar")
        
    except Exception as e:
        logging.error(f"Error durante la limpieza de mensajes: {e}")

def main() -> None:
    # Process management
    if process_manager.check_existing_process():
        logging.warning("Another bot instance is already running. Attempting to terminate it...")
        if not process_manager.kill_existing_process():
            logging.error("Failed to terminate existing process. Exiting.")
            return
    
    if not process_manager.write_pid_file():
        logging.error("Failed to write PID file. Exiting.")
        return
    
    # Setup signal handlers for graceful shutdown
    process_manager.setup_signal_handlers()
    
    logging.info("🚀 Iniciando bot avanzado con mejoras")
    logging.info(f"📋 PID: {os.getpid()}")
    logging.info(f"📁 Directorio de datos: {USER_DATA_DIR}")
    logging.info(f"🎯 Concurrency: {JOBQ.concurrency}")
    
    try:
        app = build_app()
        
        # Run cleanup on startup
        async def post_init(application):
            await cleanup_error_messages(application)
            await JOBQ.start(application.bot)
        
        app.post_init = post_init
        
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        # Cleanup on exit
        async def shutdown():
            await JOBQ.stop()
            
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(shutdown())
            else:
                loop.run_until_complete(shutdown())
        except Exception as e:
            logging.error(f"Error stopping JobQueue: {e}")

        process_manager.remove_pid_file()
        logging.info("👋 Bot detenido correctamente")

if __name__ == "__main__":
    main()
