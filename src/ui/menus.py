from telegram import InlineKeyboardButton, InlineKeyboardMarkup

ASPECT_CHOICES = ["1:1", "4:3", "3:4", "9:16", "16:9"]
BASE_CHOICES = [512, 640, 768, 896, 1024]
STEPS_CHOICES = [4, 8, 16, 32]
CFG_CHOICES = [1.0, 2.0, 4.0]

def settings_summary(s: dict, dims: tuple[int, int]) -> str:
    w, h = dims
    pre = s.get("pre_mode")
    post = s.get("post_mode")
    lcount = len(s.get("loras", []))
    return (
        f"Sampler: {s.get('sampler_name')}\n"
        f"Scheduler: {s.get('scheduler') or '-'}\n"
        f"Steps: {s.get('steps')}\n"
        f"CFG: {s.get('cfg_scale')}\n"
        f"Aspect: {s.get('aspect_ratio')} ({w}x{h})\n"
        f"Base: {s.get('base_size')}\n"
        f"n_iter: {s.get('n_iter')}\n"
        f"Pre: {pre}\n"
        f"Post: {post}\n"
        f"Loras: {lcount}"
    )

def main_menu_keyboard(s: dict) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton("Aspect", callback_data="menu:aspect"), InlineKeyboardButton("Base", callback_data="menu:base")],
        [InlineKeyboardButton("Steps", callback_data="menu:steps"), InlineKeyboardButton("CFG", callback_data="menu:cfg")],
        [InlineKeyboardButton("Sampler", callback_data="menu:sampler"), InlineKeyboardButton("Scheduler", callback_data="menu:scheduler")],
        [InlineKeyboardButton("n_iter", callback_data="menu:niter"), InlineKeyboardButton("Pre", callback_data="menu:pre")],
        [InlineKeyboardButton("Post", callback_data="menu:post"), InlineKeyboardButton("Loras", callback_data="menu:loras:0")],
    ]
    return InlineKeyboardMarkup(kb)

def submenu_keyboard_static(kind: str) -> InlineKeyboardMarkup:
    rows = []
    if kind == "aspect":
        rows = [[InlineKeyboardButton(r, callback_data=f"set:aspect:{r}")] for r in ASPECT_CHOICES]
    elif kind == "base":
        rows = [[InlineKeyboardButton(str(b), callback_data=f"set:base:{b}")] for b in BASE_CHOICES]
    elif kind == "steps":
        rows = [[InlineKeyboardButton(str(v), callback_data=f"set:steps:{v}")] for v in STEPS_CHOICES]
    elif kind == "cfg":
        rows = [[InlineKeyboardButton(str(v), callback_data=f"set:cfg:{v}")] for v in CFG_CHOICES]
    elif kind == "pre":
        rows = [
            [InlineKeyboardButton("none", callback_data="set:pre:none"), InlineKeyboardButton("random", callback_data="set:pre:random"), InlineKeyboardButton("Editar", callback_data="edit:pre")],
            [InlineKeyboardButton("preset1", callback_data="set:prepreset:0"), InlineKeyboardButton("preset2", callback_data="set:prepreset:1"), InlineKeyboardButton("preset3", callback_data="set:prepreset:2")],
            [InlineKeyboardButton("preset4", callback_data="set:prepreset:3")],
        ]
    elif kind == "post":
        rows = [
            [InlineKeyboardButton("none", callback_data="set:post:none"), InlineKeyboardButton("random", callback_data="set:post:random"), InlineKeyboardButton("Editar", callback_data="edit:post")],
            [InlineKeyboardButton("preset1", callback_data="set:postpreset:0"), InlineKeyboardButton("preset2", callback_data="set:postpreset:1"), InlineKeyboardButton("preset3", callback_data="set:postpreset:2")],
            [InlineKeyboardButton("preset4", callback_data="set:postpreset:3")],
        ]
    rows.append([InlineKeyboardButton("Volver", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)

def loras_page_keyboard(loras: list[str], selected: set[str], page: int) -> InlineKeyboardMarkup:
    per = 20
    start = page * per
    items = loras[start:start+per]
    rows = []
    for name in items:
        mark = "[x]" if name in selected else "[ ]"
        rows.append([InlineKeyboardButton(f"{mark} {name}", callback_data=f"loras:toggle:{name}:{page}")])
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("Prev", callback_data=f"loras:page:{page-1}"))
    if start + per < len(loras):
        nav.append(InlineKeyboardButton("Next", callback_data=f"loras:page:{page+1}"))
    rows.append(nav or [InlineKeyboardButton("Volver", callback_data="menu:main")])
    if nav:
        rows.append([InlineKeyboardButton("Volver", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)