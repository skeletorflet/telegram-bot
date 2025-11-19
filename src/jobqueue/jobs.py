import asyncio
import aiohttp
from dataclasses import dataclass
from typing import Optional
from io import BytesIO
from telegram import InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from services.a1111 import a1111_txt2img
from storage.users import load_user_settings
from utils.formatting import FormatText, format_generation_complete
import logging
import json
def ratio_to_dims(ratio: str, base: int) -> tuple[int, int]:
    w_str, h_str = ratio.split(":")
    w = int(w_str)
    h = int(h_str)
    def round64_up(x: float) -> int:
        return max(64, int((x + 63) // 64 * 64))
    if w >= h:
        height = base
        width = round64_up(base * (w / h))
    else:
        width = base
        height = round64_up(base * (h / w))
    return width, height

class GenJob:
    def __init__(self, user_id: int, chat_id: int, prompt: str, status_message_id: int, user_name: str, overrides: Optional[dict] = None, hr_options: Optional[dict] = None):
        self.user_id = user_id
        self.chat_id = chat_id
        self.prompt = prompt
        self.status_message_id = status_message_id
        self.user_name = user_name
        self.overrides = overrides
        self.hr_options = hr_options

class JobQueue:
    def __init__(self, concurrency: int = 2):
        self.q = asyncio.Queue()
        self.concurrency = concurrency
        self.workers = []
        self.bot = None

    async def start(self, bot):
        self.bot = bot
        for _ in range(self.concurrency):
            self.workers.append(asyncio.create_task(self._worker()))

    async def stop(self):
        for w in self.workers:
            w.cancel()
        self.workers = []

    async def enqueue(self, job: GenJob):
        await self.q.put(job)

    async def _worker(self):
        while True:
            job: GenJob = await self.q.get()
            try:
                s = load_user_settings(job.user_id)
                w, h = ratio_to_dims(s.get("aspect_ratio", "1:1"), s.get("base_size", 512))
                steps = int(s.get("steps", 4))
                cfg = float(s.get("cfg_scale", 1.0))
                sampler = s.get("sampler_name", "LCM")
                scheduler = s.get("scheduler", "")
                n_images = int(s.get("n_iter", 1))
                seed = -1
                if job.overrides:
                    steps = int(job.overrides.get("steps", steps))
                    cfg = float(job.overrides.get("cfg_scale", cfg))
                    sampler = job.overrides.get("sampler_name", sampler)
                    scheduler = job.overrides.get("scheduler", scheduler)
                    w = int(job.overrides.get("width", w))
                    h = int(job.overrides.get("height", h))
                    n_images = int(job.overrides.get("n_iter", n_images))
                    seed = int(job.overrides.get("seed", seed))
                logging.info(f"Iniciando generación con parámetros: prompt='{job.prompt[:50]}...', width={w}, height={h}, steps={steps}, cfg={cfg}, sampler={sampler}, scheduler={scheduler}, seed={seed}, n_iter={n_images}, hr_options={job.hr_options}")
                
                res = await a1111_txt2img(
                    job.prompt,
                    width=w,
                    height=h,
                    steps=steps,
                    cfg_scale=cfg,
                    sampler_name=sampler,
                    n_iter=n_images,
                    scheduler=scheduler,
                    seed=seed,
                    hr_options=job.hr_options,
                )
                logging.info(f"Generación completada. Response keys: {list(res.keys()) if res else 'None'}")
                
                imgs = res.get("images") or []
                params = res.get("parameters") or {}
                info = res.get("info") or {}
                seeds = (info or {}).get("all_seeds") or []
                
                logging.info(f"Imágenes generadas: {len(imgs)}, parámetros: {params}, info: {info}")
                if not imgs:
                    await self.bot.send_message(job.chat_id, f"{FormatText.bold(FormatText.emoji('❌ Sin imágenes generadas', '⚠️'))}", parse_mode="HTML")
                else:
                    for i, b in enumerate(imgs):
                        seed = seeds[i] if i < len(seeds) else -1
                        # Enhanced caption with better formatting and emojis
                        caption = (
                            f"{FormatText.bold(FormatText.emoji('🎨 Generación completada', '✅'))}\n\n"
                            f"{FormatText.bold('📝 Prompt:')} {FormatText.code(job.prompt[:200] + '...' if len(job.prompt) > 200 else job.prompt)}\n\n"
                            f"{FormatText.bold('⚙️ Configuración:')}\n"
                            f"• {FormatText.bold('Pasos:')} {FormatText.code(str(params.get('steps', steps)))}\n"
                            f"• {FormatText.bold('Sampler:')} {FormatText.code(params.get('sampler_name', sampler))}\n"
                            f"• {FormatText.bold('Scheduler:')} {FormatText.code(params.get('scheduler', scheduler))}\n"
                            f"• {FormatText.bold('CFG:')} {FormatText.code(str(params.get('cfg_scale', cfg)))}\n"
                            f"• {FormatText.bold('Seed:')} {FormatText.code(str(seed))}\n"
                            f"• {FormatText.bold('Tamaño:')} {FormatText.code(f'{params.get("width", w)}x{params.get("height", h)}')}\n\n"
                            f"{FormatText.bold(FormatText.emoji('👤 Autor:', ''))} {FormatText.code(job.user_name)}"
                        )
                        payload = {
                            "prompt": job.prompt,
                            "width": params.get('width', w),
                            "height": params.get('height', h),
                            "steps": params.get('steps', steps),
                            "cfg_scale": params.get('cfg_scale', cfg),
                            "sampler_name": params.get('sampler_name', sampler),
                            "scheduler": params.get('scheduler', scheduler),
                            "seed": seed,
                        }
                        rid = put_request(payload)
                        
                        # Enhanced keyboard with better buttons and emojis
                        job_data = {
                            "user_id": job.user_id,
                            "prompt": job.prompt,
                            "width": params.get('width', w),
                            "height": params.get('height', h),
                            "steps": params.get('steps', steps),
                            "cfg_scale": params.get('cfg_scale', cfg),
                            "sampler_name": params.get('sampler_name', sampler),
                            "scheduler": params.get('scheduler', scheduler),
                            "seed": seed,
                        }
                        
                        if job.hr_options:
                            kb = InlineKeyboardMarkup([
                                [InlineKeyboardButton("🔄 Repetir", callback_data=f"job:repeat:{rid}"), 
                                 InlineKeyboardButton("🔍 Final Upscale", callback_data=f"job:final:{rid}")],
                                
                            ])
                        else:
                            kb = InlineKeyboardMarkup([
                                [InlineKeyboardButton("🔄 Repetir", callback_data=f"job:repeat:{rid}"), 
                                 InlineKeyboardButton("🔍 Upscale", callback_data=f"job:upscale:{rid}")],
                                
                            ])
                        
                        # Guardar el trabajo para poder recuperarlo después
                        from storage.jobs import save_job
                        
                        # Enviar el mensaje y obtener el resultado
                        sent_message = await self._send_document_long(job.chat_id, b, f"image_{i}.png", caption, kb)
                        
                        # Guardar el file_id para upscale final
                        if sent_message and 'document' in sent_message:
                            job_data['file_id'] = sent_message['document']['file_id']
                            job_data['message_id'] = sent_message['message_id']
                            
                            # Guardar el trabajo usando el message_id real del mensaje enviado
                            save_job(sent_message['message_id'], job_data)
            except Exception as e:
                logging.error(f"Error en generación para job {job}: {str(e)}", exc_info=True)
                error_msg = f"{FormatText.bold(FormatText.emoji('❌ Error en generación', '⚠️'))}\n{FormatText.code(str(e))}"
                await self.bot.send_message(job.chat_id, error_msg, parse_mode="HTML")
            finally:
                if job.status_message_id:
                    try:
                        await self.bot.delete_message(chat_id=job.chat_id, message_id=job.status_message_id)
                    except Exception as e:
                        logging.warning(f"No se pudo borrar el mensaje de estado {job.status_message_id}: {e}")
                self.q.task_done()

    async def _send_document_long(self, chat_id: int, img_bytes: bytes, filename: str, caption: str, kb: InlineKeyboardMarkup | None) -> dict:
        url = f"https://api.telegram.org/bot{self.bot.token}/sendDocument"
        attempt = 0
        while True:
            form = aiohttp.FormData()
            form.add_field("chat_id", str(chat_id))
            form.add_field("caption", caption)
            form.add_field("parse_mode", "HTML")
            if kb:
                form.add_field("reply_markup", json.dumps(kb.to_dict()))
            form.add_field("document", img_bytes, filename=filename, content_type="image/png")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, data=form) as resp:
                        resp.raise_for_status()
                        result = await resp.json()
                        if not result.get("ok"):
                            logging.error(f"Telegram API error: {result}")
                            raise Exception(f"Telegram API error: {result.get('description', 'Unknown error')}")
                        return result.get("result", {})
            except Exception as e:
                attempt += 1
                logging.error(f"Error en _send_document_long (attempt {attempt}): {str(e)}")
                if attempt >= 3:
                    raise
                await asyncio.sleep(5 * attempt)

# Simple in-memory request store for callbacks
_REQ_STORE = {}

def put_request(payload: dict) -> str:
    rid = str(id(payload)) + ":" + str(asyncio.get_event_loop().time())
    _REQ_STORE[rid] = payload
    return rid

def get_request(rid: str) -> dict | None:
    return _REQ_STORE.get(rid)
