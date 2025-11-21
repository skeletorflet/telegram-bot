
async def fetch_schedulers() -> list[dict]:
    try:
        data = await a1111_get_json("/sdapi/v1/schedulers")
        return [
            {"name": x.get("name"), "label": x.get("label") or x.get("name")}
            for x in data
            if isinstance(x, dict) and x.get("name")
        ]
    except Exception:
        return []

async def fetch_loras() -> list[str]:
    data = await a1111_get_json("/sdapi/v1/loras")
    names = []
    for x in data:
        n = x.get("name") or x.get("model_name") or x.get("path")
        if n:
            names.append(n)
    return names

async def a1111_txt2img(prompt: str, width: int = 512, height: int = 512, steps: int = 4, cfg_scale: float = 1.0, sampler_name: str = "LCM", n_iter: int = 1, scheduler: str = "") -> bytes:
    payload = {
        "prompt": prompt,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "width": width,
        "height": height,
        "sampler_name": sampler_name,
        "n_iter": max(1, min(8, n_iter)),
        "batch_size": 1,
    }
    if scheduler:
        payload["scheduler"] = scheduler
    url = f"{A1111_URL}/sdapi/v1/txt2img"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=600)) as resp:
            resp.raise_for_status()
            data = await resp.json()
            img_b64 = data["images"][0]
            return base64.b64decode(img_b64)

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
    prompt = compose_prompt(settings, prompt_raw)
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
        await JOBQ.enqueue(GenJob(user_id=user_id, chat_id=update.effective_chat.id, prompt=prompt, status_message_id=status_message.message_id, user_name=update.effective_user.first_name))
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

def settings_summary(s: dict) -> str:
    w, h = ratio_to_dims(s.get("aspect_ratio", "1:1"), s.get("base_size", 512))
    pre_count = len(s.get("pre_modifiers", []))
    post_count = len(s.get("post_modifiers", []))
    lcount = len(s.get("loras", []))
    return (
        f"🎨 Sampler: {s.get('sampler_name')}\n"
        f"⏰ Scheduler: {s.get('scheduler') or '-'}\n"
        f"⚡ Steps: {s.get('steps')}\n"
        f"🎛️ CFG: {s.get('cfg_scale')}\n"
        f"📐 Aspect: {s.get('aspect_ratio')} ({w}x{h})\n"
        f"📏 Base: {s.get('base_size')}\n"
        f"🔢 Imagenes: {s.get('n_iter')}\n"
        f"🎲 Pre: {pre_count} activados\n"
        f"✨ Post: {post_count} activados\n"
        f"🎭 Loras: {lcount}"
    )

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

def main_menu_keyboard(s: dict, is_compliant: bool) -> InlineKeyboardMarkup:
    icon = "✅" if is_compliant else "🔴"
    kb = [
        [InlineKeyboardButton("📐 Aspect", callback_data="menu:aspect"), InlineKeyboardButton("📏 Base", callback_data="menu:base")],
        [InlineKeyboardButton("⚡ Steps", callback_data="menu:steps"), InlineKeyboardButton("🎛️ CFG", callback_data="menu:cfg")],
        [InlineKeyboardButton("🎨 Sampler", callback_data="menu:sampler"), InlineKeyboardButton("⏰ Scheduler", callback_data="menu:scheduler")],
        [InlineKeyboardButton("🔢 Imagenes", callback_data="menu:niter"), InlineKeyboardButton("🎲 Pre", callback_data="menu:pre")],
        [InlineKeyboardButton("✨ Post", callback_data="menu:post"), InlineKeyboardButton("🎭 Loras", callback_data="menu:loras:0")],
        [InlineKeyboardButton(f"{icon} Auto Configurar", callback_data="menu:autoconfig")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="menu:close")],
    ]
    return InlineKeyboardMarkup(kb)

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    s = load_user_settings(user_id)
    try:
        model_name = await get_current_model()
        preset = get_preset_for_model(model_name)
    except Exception as e:
        logging.warning(f"A1111 offline: {e}")
        model_name = None
        preset = None
    is_compliant = are_settings_compliant(s, preset)
    await update.message.reply_text(settings_summary(s), reply_markup=main_menu_keyboard(s, is_compliant))

def submenu_keyboard_static(kind: str, preset: Preset) -> InlineKeyboardMarkup:
    rows = []
    if kind == "aspect":
        rows = [[InlineKeyboardButton(r, callback_data=f"set:aspect:{r}")] for r in ASPECT_CHOICES]
    elif kind == "base":
        recommended = preset.resolutions if preset else []
        rows = [[InlineKeyboardButton(f"{str(b)} {'👌' if b in recommended else ''}".strip(), callback_data=f"set:base:{b}")] for b in BASE_CHOICES]
    elif kind == "steps":
        recommended = preset.steps if preset else []
        rows = [[InlineKeyboardButton(f"{str(v)} {'👌' if v in recommended else ''}".strip(), callback_data=f"set:steps:{v}")] for v in STEPS_CHOICES]
    elif kind == "cfg":
        recommended = preset.cfg if preset else []
        rows = [[InlineKeyboardButton(f"{str(v)} {'👌' if v in recommended else ''}".strip(), callback_data=f"set:cfg:{v}")] for v in CFG_CHOICES]
    elif kind == "niter":
        rows = [[InlineKeyboardButton(str(v), callback_data=f"set:niter:{v}")] for v in range(1, 9)]
    rows.append([InlineKeyboardButton("Volver", callback_data="menu:main"), InlineKeyboardButton("Cerrar", callback_data="menu:close")])
    return InlineKeyboardMarkup(rows)

def loras_page_keyboard(loras: list[str], selected: set[str], page: int) -> InlineKeyboardMarkup:
    per = 20
    start = page * per
    items = loras[start:start+per]
    rows = []
    for name in items:
        mark = "✅" if name in selected else "⛔️"
        rows.append([InlineKeyboardButton(f"{mark} {name}", callback_data=f"loras:toggle:{name}:{page}")])
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("Prev", callback_data=f"loras:page:{page-1}"))
    if start + per < len(loras):
        nav.append(InlineKeyboardButton("Next", callback_data=f"loras:page:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("Volver", callback_data="menu:main"), InlineKeyboardButton("Cerrar", callback_data="menu:close")])
    return InlineKeyboardMarkup(rows)

def modifiers_page_keyboard(kind: str, modifiers: list[str], selected: set[str], page: int) -> InlineKeyboardMarkup:
    per = 10  # Show 10 modifiers per page
    start = page * per
    items = modifiers[start:start+per]
    rows = []
    for name in items:
        mark = "✅" if name in selected else "⛔️"
        rows.append([InlineKeyboardButton(f"{mark} {name}".strip(), callback_data=f"mod:{kind}:toggle:{name}:{page}")])
    
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"mod:{kind}:page:{page-1}"))
    if start + per < len(modifiers):
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"mod:{kind}:page:{page+1}"))
    
    if nav:
        rows.append(nav)
    
    rows.append([InlineKeyboardButton("⬅️ Volver", callback_data="menu:main"), InlineKeyboardButton("❌ Cerrar", callback_data="menu:close")])
    return InlineKeyboardMarkup(rows)


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
        "loras": "🎭 Administra tus Loras (modelos mágicos que modifican el estilo). ✨"
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

            save_user_settings(user_id, s)
            
            await q.answer("✅ Configuración automática aplicada")
            
            # Update the message with new settings
            text = settings_summary(s)
            # After autoconfig, settings are compliant
            kb = main_menu_keyboard(s, is_compliant=True)
            await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            return
        if kind == "main":
            is_compliant = are_settings_compliant(s, preset)
            await q.edit_message_text(settings_summary(s), reply_markup=main_menu_keyboard(s, is_compliant))
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
                    kb = main_menu_keyboard(s)
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
        await q.edit_message_text(settings_summary(s), reply_markup=main_menu_keyboard(s, is_compliant))
        
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
    if data.startswith("edit:"):
        parts = data.split(":")
        action = parts[1]
        if action in {"pre", "post"}:
            context.chat_data["edit_target"] = action
            await q.answer()
            await q.edit_message_text(f"Escribe el texto para {action}_value. Usa /cancel para cancelar.")
            return
        if action == "confirm":
            target = parts[2]
            candidate = context.chat_data.get("edit_candidate", "").strip()
            if not candidate:
                await q.answer()
                await q.edit_message_text("El texto está vacío.", reply_markup=main_menu_keyboard(s))
                context.chat_data.clear()
                return
            if len(candidate) > 1000:
                candidate = candidate[:1000]
            if target == "pre":
                s["pre_value"] = candidate
                s["pre_mode"] = "custom"
            else:
                s["post_value"] = candidate
                s["post_mode"] = "custom"
            save_user_settings(user_id, s)
            context.chat_data.clear()
            tip = ("Pre" if target == "pre" else "Post") + ": " + _truncate(candidate)
            await q.answer(tip)
            await q.edit_message_text(settings_summary(s), reply_markup=main_menu_keyboard(s))
            return
        if action == "cancel":
            context.chat_data.clear()
            await q.answer("Cancelado")
            await q.edit_message_text(settings_summary(s), reply_markup=main_menu_keyboard(s))
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
            logging.info(f"Ejecutando REPEAT con seed aleatorio")
            overrides = {
                "steps": steps_p,
                "cfg_scale": cfg_p,
                "sampler_name": sampler_p,
                "scheduler": sched_p,
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
            await JOBQ.enqueue(GenJob(user_id=user_id, chat_id=update.effective_chat.id, prompt=prompt_p, overrides=overrides, status_message_id=status_message.message_id, user_name=update.effective_user.first_name))
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
                "alwayson_scripts": {
                    "ADetailer": {
                        "args": [
                            {"ad_model": "face_yolov8n.pt"},
                            {"ad_model": "mediapipe_face_short"},
                            {"ad_model": "mediapipe_face_mesh_eyes_only"},
                        ]
                    }
                }
            }
            logging.info(f"upscale action overrides: {overrides}, hr: {hr}")
            # Enhanced upscale message
            upscale_message = (
                f"{FormatText.bold(FormatText.emoji('🔍 Upscale HR encolado', '✅'))}\n"
                f"{FormatText.bold('Prompt:')} {FormatText.code(prompt_p[:100] + '...' if len(prompt_p) > 100 else prompt_p)}\n"
                f"{FormatText.bold('Factor:')} {FormatText.code('1.5x')}\n"
                f"{FormatText.bold('Upscaler:')} {FormatText.code('R-ESRGAN 4x+')}\n"
                f"{FormatText.bold('Denoising:')} {FormatText.code('0.3')}\n\n"
                f"{FormatText.italic('Generando versión de alta resolución...')}"
            )
            status_message = await update.effective_chat.send_message(upscale_message, parse_mode="HTML")
            await JOBQ.enqueue(GenJob(user_id=user_id, chat_id=update.effective_chat.id, prompt=prompt_p, overrides=overrides, hr_options=hr, status_message_id=status_message.message_id, user_name=update.effective_user.first_name))
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
            await JOBQ.enqueue(GenJob(user_id=user_id, chat_id=update.effective_chat.id, prompt=prompt_p, overrides=overrides, status_message_id=status_message.message_id, user_name=update.effective_user.first_name))
            await q.answer("Nuevo seed en cola")
            return
        if action == "final":
            logging.info(f"=== INICIANDO FINAL UPSCALE ===")
            logging.info(f"Ejecutando FINAL UPSCALE - data={data}, user_id={user_id}")
            
            try:
                # Test connection to A1111 API first
                from services.a1111 import a1111_test_connection
                connection_ok = await a1111_test_connection()
                if not connection_ok:
                    logging.error("No se pudo conectar a la API de A1111")
                    await q.answer("Error: No se pudo conectar a A1111")
                    return
                
                logging.info("Conexión a A1111 exitosa, procediendo con FINAL UPSCALE")
                await q.answer("⏳ Realizando upscale final... por favor espera.")
                    
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
                        await q.answer("Expirado")
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
                    await q.answer("Error al descargar imagen")
                    return
                
                logging.info(f"Llamando a a1111_extra_single_image con {len(img_bytes)} bytes")
                logging.info(f"Parámetros del upscale: upscaler_1='R-ESRGAN 4x+', upscaling_resize=2")
                
                # Verificar que los bytes de imagen sean válidos
                if not img_bytes or len(img_bytes) < 100:
                    logging.error(f"Imagen descargada inválida: {len(img_bytes)} bytes")
                    await q.answer("Error: imagen descargada inválida")
                    return
                
                # Importar la función aquí para asegurar que esté disponible
                from services.a1111 import a1111_extra_single_image
                logging.info("Función a1111_extra_single_image importada correctamente")
                
                out = await a1111_extra_single_image(img_bytes, upscaler_1="R-ESRGAN 4x+", upscaling_resize=2)
                logging.info(f"Resultado del upscale: {len(out) if out else 0} bytes")
                
                if not out:
                    logging.error("Upscale resultó en imagen vacía")
                    await q.answer("Error en upscale")
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
                await q.answer("Finalizado")
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
                
                await q.answer(f"Error crítico en upscale: {error_details[:100]}")
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
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        # Cleanup on exit
        process_manager.remove_pid_file()
        logging.info("👋 Bot detenido correctamente")

if __name__ == "__main__":
    main()