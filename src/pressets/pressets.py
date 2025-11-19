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

# --- Mapeo de modelos a sus presets ---
# La clave es una subcadena del nombre del archivo del modelo para que coincida
# Ejemplo: "dreamshaper" coincidirá con "dreamshaper_8_93211.safetensors"
PRESETS = {
    "dreamshaper": DREAMSHAPER_PRESET,
}

def get_preset_for_model(model_name: str) -> Preset:
    """
    Busca y devuelve el preset más adecuado para un nombre de modelo dado.

    Args:
        model_name: El nombre del archivo del checkpoint del modelo (ej. "dreamshaper_8.safetensors").

    Returns:
        El objeto Preset correspondiente o el preset por defecto si no se encuentra uno.
    """
    if not model_name:
        return DEFAULT_PRESET

    model_name_lower = model_name.lower()
    for key, preset in PRESETS.items():
        if key in model_name_lower:
            return preset
    
    return DEFAULT_PRESET