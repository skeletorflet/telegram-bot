from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pressets.pressets import Preset
from utils.common import ratio_to_dims
from constants import ASPECT_CHOICES, BASE_CHOICES, STEPS_CHOICES, CFG_CHOICES

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
        [InlineKeyboardButton("🖼️ Modelo", callback_data="menu:model:0"), InlineKeyboardButton(f"{icon} Auto Configurar", callback_data="menu:autoconfig")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="menu:close")],
    ]
    return InlineKeyboardMarkup(kb)

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

def models_page_keyboard(models: list, current_model: str, page: int = 0) -> InlineKeyboardMarkup:
    kb = []
    PAGE_SIZE = 5
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    for model in models[start:end]:
        is_current = model.get("model_name", "") == current_model
        text = f"✅ {model['title']}" if is_current else model['title']
        kb.append([InlineKeyboardButton(text, callback_data=f"set:model:{model['model_name']}")])
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("<<", callback_data=f"menu:model:{page-1}"))
    if end < len(models):
        nav.append(InlineKeyboardButton(">>", callback_data=f"menu:model:{page+1}"))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton("⬅️ Atrás", callback_data="menu:main")])
    return InlineKeyboardMarkup(kb)

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