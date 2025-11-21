import asyncio
import aiohttp
from dataclasses import dataclass
from typing import Optional
from io import BytesIO
from telegram import InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from services.a1111 import a1111_txt2img, a1111_get_progress, get_current_model
from pressets.pressets import get_preset_for_model
from storage.users import load_user_settings
from utils.formatting import FormatText, format_generation_complete
import logging
import json
from utils.common import ratio_to_dims

class GenJob:
    def __init__(self, user_id: int, chat_id: int, prompt: str, status_message_id: int, user_name: str, overrides: Optional[dict] = None, hr_options: Optional[dict] = None, alwayson_scripts: Optional[dict] = None, operation_type: str = "txt2img", operation_metadata: Optional[dict] = None):
        self.user_id = user_id
        self.chat_id = chat_id
        self.prompt = prompt
        self.status_message_id = status_message_id
        self.user_name = user_name
        self.overrides = overrides
        self.hr_options = hr_options
        self.alwayson_scripts = alwayson_scripts
        self.operation_type = operation_type  # "txt2img", "upscale_hr", "repeat", "newseed"
        self.operation_metadata = operation_metadata or {}  # Additional context for messages

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

    async def _progress_loop(self, job: GenJob):
        last_progress = -1
        has_started = False  # Track if we've confirmed this job is being processed
        consecutive_progress_count = 0  # Count consecutive progress updates
        
        # Operation titles
        operation_titles = {
            "txt2img": ("🎨", "Generando Imagen"),
            "upscale_hr": ("🔍", "Generando con Upscale HR"),
            "repeat": ("🔄", "Repitiendo Generación"),
            "newseed": ("🎲", "Nueva Variación")
        }
        emoji, title = operation_titles.get(job.operation_type, ("🎨", "Generando"))
        
        # Show queued message immediately on first check
        queued_msg = (
            f"{FormatText.bold(FormatText.emoji(f'{emoji} {title}', '⏳'))}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"{FormatText.bold('📋 Estado:')} {FormatText.code('En cola...')}\n\n"
            f"{FormatText.italic('⏰ Esperando turno para procesar...')}"
        )
        
        try:
            await self.bot.edit_message_text(
                chat_id=job.chat_id,
                message_id=job.status_message_id,
                text=queued_msg,
                parse_mode="HTML"
            )
        except Exception as e:
            logging.warning(f"Failed to show initial queued status: {e}")
        
        while True:
            await asyncio.sleep(1.5)
            try:
                prog_data = await a1111_get_progress()
                progress = prog_data.get("progress", 0)
                eta = prog_data.get("eta_relative", 0)
                
                # Only consider job as "started" if we see consistent progress
                # This prevents showing progress from other jobs in the queue
                if progress > 0:
                    consecutive_progress_count += 1
                    # Require at least 2 consecutive progress updates to confirm it's our job
                    if consecutive_progress_count >= 2:
                        has_started = True
                else:
                    consecutive_progress_count = 0
                    # If we had started but now have no progress, keep showing as started
                    # (this handles brief gaps in progress reporting)
                
                # If job hasn't started, keep showing queued message
                if not has_started:
                    # Message already shown initially, just continue waiting
                    continue
                
                # Only show progress if job has started and progress changed significantly
                if has_started and progress > 0 and (progress - last_progress > 0.05 or int(progress * 20) != int(last_progress * 20)):
                    last_progress = progress
                    bar_len = 10
                    filled = int(progress * bar_len)
                    bar = "▓" * filled + "░" * (bar_len - filled)
                    pct = int(progress * 100)
                    
                    # Extract step info from state
                    state = prog_data.get("state", {})
                    current_step = state.get("sampling_step", 0)
                    total_steps = state.get("sampling_steps", 0)
                    job_no = state.get("job_no", 0)
                    job_count = state.get("job_count", 0)
                    
                    # Operation-specific titles and emojis
                    operation_titles = {
                        "txt2img": ("🎨", "Generando Imagen"),
                        "upscale_hr": ("🔍", "Generando con Upscale HR"),
                        "repeat": ("🔄", "Repitiendo Generación"),
                        "newseed": ("🎲", "Nueva Variación")
                    }
                    
                    emoji, title = operation_titles.get(job.operation_type, ("🎨", "Generando"))
                    
                    # Build enhanced message with visual separator
                    # Use final_prompt if available (with pre/post prompts), otherwise use original
                    display_prompt = getattr(job, 'final_prompt', job.prompt)
                    prompt_preview = display_prompt[:45] + "..." if len(display_prompt) > 45 else display_prompt
                    
                    msg_parts = [
                        f"{FormatText.bold(FormatText.emoji(f'{emoji} {title}', '⏳'))}",
                        "━━━━━━━━━━━━━━━━━━━━",
                        f"{FormatText.code(f'[{bar}] {pct}%')}"
                    ]
                    
                    # Progress section
                    progress_info = []
                    if total_steps > 0:
                        progress_info.append(f"Step: {FormatText.code(f'{current_step}/{total_steps}')}")
                    if job_count > 1:
                        progress_info.append(f"Imagen: {FormatText.code(f'{job_no}/{job_count}')}")
                    if eta > 0:
                        progress_info.append(f"ETA: {FormatText.code(f'~{int(eta)}s')}")
                    
                    if progress_info:
                        msg_parts.append("")
                        msg_parts.append(f"{FormatText.bold('📊 Progreso:')}")
                        for info in progress_info:
                            msg_parts.append(f"  • {info}")
                    
                    # Configuration section (if metadata available)
                    if job.operation_metadata:
                        msg_parts.append("")
                        msg_parts.append(f"{FormatText.bold('🔧 Configuración:')}")
                        
                        if "hr_scale" in job.operation_metadata:
                            hr_scale_val = f"{job.operation_metadata['hr_scale']}x"
                            msg_parts.append(f"  • Factor: {FormatText.code(hr_scale_val)}")
                        if "upscaler" in job.operation_metadata:
                            msg_parts.append(f"  • Upscaler: {FormatText.code(job.operation_metadata['upscaler'])}")
                        if "denoising" in job.operation_metadata:
                            msg_parts.append(f"  • Denoising: {FormatText.code(str(job.operation_metadata['denoising']))}")
                    
                    # Prompt preview
                    msg_parts.append("")
                    msg_parts.append(f"{FormatText.italic(f'💬 {prompt_preview}')}")
                    
                    msg = "\n".join(msg_parts)
                    
                    try:
                        await self.bot.edit_message_text(
                            chat_id=job.chat_id,
                            message_id=job.status_message_id,
                            text=msg,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        if "not modified" not in str(e).lower():
                            logging.warning(f"Failed to update progress: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in progress loop: {e}")

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
                logging.info(f"Iniciando generación con parámetros: prompt='{job.prompt[:50]}...', width={w}, height={h}, steps={steps}, cfg={cfg}, sampler={sampler}, scheduler={scheduler}, seed={seed}, n_iter={n_images}, hr_options={job.hr_options}, alwayson_scripts={job.alwayson_scripts}")
                
                # Get current model and its preset to apply pre/post/negative prompts
                current_model = await get_current_model()
                preset = get_preset_for_model(current_model) if current_model else None
                
                # Build final prompt with preset pre/post prompts
                final_prompt = job.prompt
                negative_prompt = ""
                
                if preset:
                    if preset.pre_prompt:
                        final_prompt = f"{preset.pre_prompt}, {final_prompt}"
                    if preset.post_prompt:
                        final_prompt = f"{final_prompt}, {preset.post_prompt}"
                    negative_prompt = preset.negative_prompt
                    logging.info(f"Preset '{preset.model_name}' aplicado: pre_prompt={bool(preset.pre_prompt)}, post_prompt={bool(preset.post_prompt)}, negative_prompt={bool(preset.negative_prompt)}")
                
                # Store final_prompt in job so progress messages show it
                job.final_prompt = final_prompt
                
                # Start progress loop
                progress_task = asyncio.create_task(self._progress_loop(job))
                
                try:
                    res = await a1111_txt2img(
                        final_prompt,
                        width=w,
                        height=h,
                        steps=steps,
                        cfg_scale=cfg,
                        sampler_name=sampler,
                        n_iter=n_images,
                        scheduler=scheduler,
                        seed=seed,
                        negative_prompt=negative_prompt,
                        hr_options=job.hr_options,
                        alwayson_scripts=job.alwayson_scripts,
                    )
                finally:
                    progress_task.cancel()
                    try:
                        await progress_task
                    except asyncio.CancelledError:
                        pass
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
                        size_str = f"{params.get('width', w)}x{params.get('height', h)}"
                        caption = (
                            f"{FormatText.bold(FormatText.emoji('🎨 Generación completada', '✅'))}\n\n"
                            f"{FormatText.bold('📝 Prompt:')} {FormatText.code(job.prompt)}\n\n"
                            f"{FormatText.bold('⚙️ Configuración:')}\n"
                            f"• {FormatText.bold('Pasos:')} {FormatText.code(str(params.get('steps', steps)))}\n"
                            f"• {FormatText.bold('Sampler:')} {FormatText.code(params.get('sampler_name', sampler))}\n"
                            f"• {FormatText.bold('Scheduler:')} {FormatText.code(params.get('scheduler', scheduler))}\n"
                            f"• {FormatText.bold('CFG:')} {FormatText.code(str(params.get('cfg_scale', cfg)))}\n"
                            f"• {FormatText.bold('Seed:')} {FormatText.code(str(seed))}\n"
                            f"• {FormatText.bold('Tamaño:')} {FormatText.code(size_str)}\n\n"
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

    async def _send_document_long(self, chat_id: int, img_bytes: bytes, filename: str, caption: str, kb: Optional[InlineKeyboardMarkup]) -> dict:
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

def get_request(rid: str) -> Optional[dict]:
    return _REQ_STORE.get(rid)
