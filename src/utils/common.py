def ratio_to_dims(ratio: str, base: int) -> tuple[int, int]:
    """Calcula las dimensiones (ancho, alto) basadas en un ratio y un tamaño base."""
    try:
        w_str, h_str = ratio.split(":")
        w = int(w_str)
        h = int(h_str)
    except ValueError:
        # Fallback por si el ratio no es válido
        return base, base

    def round64_up(x: float) -> int:
        return max(64, int((x + 63) // 64 * 64))

    if w >= h:
        height = base
        width = round64_up(base * (w / h))
    else:
        width = base
        height = round64_up(base * (h / w))
    return width, height

def truncate_text(text: str, limit: int = 60) -> str:
    """Corta el texto si excede el límite y añade puntos suspensivos."""
    if not isinstance(text, str):
        return ""
    return text if len(text) <= limit else text[:limit] + "…"
