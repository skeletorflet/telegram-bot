from typing import List, Optional, Tuple

class Preset:
    """
    Define los parámetros recomendados para un modelo específico de Stable Diffusion.
    """
    def __init__(self,
                 model_name: str,
                 steps: List[int],
                 cfg: List[float],
                 samplers: List[str],
                 schedulers: List[str],
                 resolutions: List[int]):  # Cambiado a List[int]
        self.model_name = model_name
        self.steps = steps
        self.cfg = cfg
        self.samplers = samplers
        self.schedulers = schedulers
        self.resolutions = resolutions

# --- Definición de Presets para cada modelo ---

# Preset por defecto si no se encuentra uno específico para el modelo
DEFAULT_PRESET = Preset(
    model_name="Default",
    steps=[20, 25],
    cfg=[7.0, 7.5],
    samplers=["Euler a", "DPM++ 2M Karras"],
    schedulers=["Automatic", "Karras"],
    resolutions=[512, 768]  # Simplificado
)

# Preset para el modelo Dreamshaper
DREAMSHAPER_PRESET = Preset(
    model_name="dreamshaper",
    steps=[25, 30, 35],
    cfg=[7.0, 7.5, 8.0],
    samplers=["DPM++ 2M Karras", "DPM++ SDE Karras", "Euler a"],
    schedulers=["Automatic", "Karras"],
    resolutions=[512, 768, 640]  # Simplificado
)

# Preset para el modelo Janku
JANKU_PRESET = Preset(
    model_name="janku",
    steps=[25, 30],
    cfg=[3, 5],
    samplers=["Euler", "Euler a"],
    schedulers=["Normal", "Simple"],
    resolutions=[768, 1024]  # Simplificado
)

# Preset para el modelo WAI Illustrious
WAI_ILLUSTRIOUS_PRESET = Preset(
    model_name="waiIllustrious",
    steps=[15, 20, 25, 30],
    cfg=[5, 7],
    samplers=["Euler a"],
    schedulers=["Normal"],
    resolutions=[1024]  # Simplificado
)


# Preset para el modelo Hassaku
HASSAKU_PRESET = Preset(
    model_name="hassaku",
    steps=[25, 30],
    cfg=[3, 5],
    samplers=["Euler", "Euler a"],
    schedulers=["Normal", "Simple"],
    resolutions=[768, 1024]  # Simplificado
)


# --- Mapeo de modelos a sus presets ---
# La clave es una subcadena del nombre del archivo del modelo para que coincida
# Ejemplo: "dreamshaper" coincidirá con "dreamshaper_8_93211.safetensors"
PRESETS = {
    "dreamshaper": DREAMSHAPER_PRESET,
    "janku": JANKU_PRESET,
    "wai_illustrious": WAI_ILLUSTRIOUS_PRESET,
    "hassaku": HASSAKU_PRESET,
}

def get_preset_for_model(model_name: str) -> Optional[Preset]:
    """
    Busca y devuelve el preset más adecuado para un nombre de modelo dado.
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
    if not (min(preset.steps) <= settings.get("steps", 0) <= max(preset.steps)):
        return False
        
    if not (min(preset.cfg) <= settings.get("cfg_scale", 0.0) <= max(preset.cfg)):
        return False
        
    # Para resolución, verificamos si el 'base_size' está en la lista de resoluciones permitidas.
    if settings.get("base_size") not in preset.resolutions:
        return False
        
    if settings.get("sampler_name") not in preset.samplers:
        return False

    return True