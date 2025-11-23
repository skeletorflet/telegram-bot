from typing import List, Optional, Tuple

class Preset:
    """
    Define los parámetros recomendados para un modelo específico de Stable Diffusion.
    Incluye opciones para pre/post prompts y negative prompt preestablecidos.
    """
    def __init__(self,
                 model_name: str,
                 steps: List[int],
                 cfg: List[float],
                 samplers: List[str],
                 schedulers: List[str],
                 resolutions: List[int],
                 pre_prompt: str = "",  # Texto que se añade ANTES del prompt del usuario
                 post_prompt: str = "",  # Texto que se añade DESPUÉS del prompt del usuario
                 negative_prompt: str = ""):  # Negative prompt preestablecido para este preset
        self.model_name = model_name
        self.steps = steps
        self.cfg = cfg
        self.samplers = samplers
        self.schedulers = schedulers
        self.resolutions = resolutions
        self.pre_prompt = pre_prompt
        self.post_prompt = post_prompt
        self.negative_prompt = negative_prompt

# --- Definición de Presets para cada modelo ---

# Preset por defecto si no se encuentra uno específico para el modelo
DEFAULT_PRESET = Preset(
    model_name="Default",
    steps=[20, 25],
    cfg=[7.0, 7.5],
    samplers=["Euler a", "DPM++ 2M Karras"],
    schedulers=["Automatic", "Karras"],
    resolutions=[512, 768]
)

# Preset para el modelo Dreamshaper
DREAMSHAPER_PRESET = Preset(
    model_name="dreamshaper",
    steps=[25, 30, 35],
    cfg=[7.0, 7.5, 8.0],
    samplers=["DPM++ 2M Karras", "DPM++ SDE Karras", "Euler a"],
    schedulers=["Automatic", "Karras"],
    resolutions=[512, 768, 640]
)

# Preset para el modelo Janku
JANKU_PRESET = Preset(
    model_name="janku",
    steps=[25, 30],
    cfg=[3, 5],
    samplers=["Euler", "Euler a"],
    schedulers=["Normal", "Simple"],
    resolutions=[768, 1024],
    post_prompt="masterpiece, best quality, very aesthetic",
    negative_prompt="lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry"
)

# Preset para el modelo WAI Illustrious
WAI_ILLUSTRIOUS_PRESET = Preset(
    model_name="waiIllustrious",
    steps=[25, 30],
    cfg=[5, 7],
    samplers=["Euler a"],
    schedulers=["Normal"],
    resolutions=[1024],
    pre_prompt="(4k,8k,Ultra HD), masterpiece, best quality, ultra-detailed, very aesthetic, depth of field, best lighting, detailed illustration, detailed background, cinematic",
    negative_prompt="(worst quality, low quality, extra digits:1.4),(extra fingers), (bad hands), missing fingers, child, loli, (watermark), censored, sagging breasts"
)

# Preset para el modelo Hassaku
HASSAKU_PRESET = Preset(
    model_name="hassaku",
    steps=[25, 30],
    cfg=[3, 5],
    samplers=["Euler", "Euler a"],
    schedulers=["Normal", "Simple"],
    resolutions=[768, 1024],
    post_prompt="masterpiece, best quality, very aesthetic, absurdres",
    negative_prompt="lowres, (bad), text, error, fewer, extra, missing, worst quality, jpeg artifacts, low quality, watermark, unfinished, displeasing, oldest, early, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract]"
)

# Preset para el modelo Juggernaut
JUGGERNAUT_PRESET = Preset(
    model_name="juggernaut",
    steps=[30, 40],
    cfg=[3, 6],
    samplers=["DPM++ 2M SDE"],
    schedulers=[" Karras"],
    resolutions=[1024],
    post_prompt="masterpiece, best quality, very aesthetic, absurdres",
    negative_prompt="lowres, (bad), text, error, fewer, extra, missing, worst quality, jpeg artifacts, low quality, watermark, unfinished, displeasing, oldest, early, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract]"
)

# Perfect Illustrious (nota: el nombre real del modelo tiene typo 'prefect' no 'perfect')
PERFECT_ILLUSTRIOUS_PRESET = Preset(
    model_name="prefectIllustrious",
    steps=[25, 30],
    cfg=[5, 6],
    samplers=["Euler a", "DPM++ 2M"],
    schedulers=["Normal"],
    resolutions=[1024],
    pre_prompt="masterpiece,best quality,amazing quality,absurdres",
    negative_prompt="bad quality,worst quality,worst detail,sketch,censored,watermark, signature, artist name"
)

# IlustMix Presset
ILUSTMIX_PRESET = Preset(
    model_name="ilustmix",
    steps=[25, 30],
    cfg=[3.5, 7],
    samplers=["Euler a"],
    schedulers=["Normal"],
    resolutions=[1024],
    pre_prompt="masterpiece, best quality, amazing quality, very aesthetic, detailed eyes, perfect eyes, realistic eyes",
    negative_prompt="bad quality,worst quality,worst detail,sketch,censored,watermark, signature, artist name"
)

# --- Mapeo de modelos a sus presets ---
# La clave es una subcadena del nombre del archivo del modelo para que coincida
# Ejemplo: "dreamshaper" coincidirá con "dreamshaper_8_93211.safetensors"
PRESETS = {
    "dreamshaper": DREAMSHAPER_PRESET,
    "janku": JANKU_PRESET,
    "wai_illustrious": WAI_ILLUSTRIOUS_PRESET,
    "waiillustrious": WAI_ILLUSTRIOUS_PRESET,  # Alias sin underscore
    "hassaku": HASSAKU_PRESET,
    "juggernaut": JUGGERNAUT_PRESET,
    "prefectillustrious": PERFECT_ILLUSTRIOUS_PRESET,  # Coincide con el modelo real (tiene typo)
    "perfectillustrious": PERFECT_ILLUSTRIOUS_PRESET,  # También coincide con la escritura correcta
}

def get_preset_for_model(model_name: str) -> Optional[Preset]:
    """
    Busca y devuelve el preset más congruo para un nombre de modelo dado.
    La búsqueda es flexible, ignorando mayúsculas/minúsculas y caracteres especiales.

    Args:
        model_name: El nombre del checkpoint del modelo.

    Returns:
        El objeto Preset correspondiente o None si no se encuentra.
    """
    if not model_name:
        return None

    def normalize(name: str) -> str:
        return name.lower().replace("_", "").replace("-", "").replace(" ", "")

    normalized_model_name = normalize(model_name)

    for preset_key, preset_obj in PRESETS.items():
        if normalize(preset_key) in normalized_model_name:
            return preset_obj
            
    return None

def are_settings_compliant(settings: dict, preset: Optional[Preset]) -> bool:
    """
    Verifica si la configuración del usuario es compatible con un preset de modelo.

    Args:
        settings: El diccionario de configuración del usuario.
        preset: El objeto Preset a comprobar. Si es None, devuelve False.

    Returns:
        True si la configuración es compatible, False en caso contrario.
    """
    if not preset:
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