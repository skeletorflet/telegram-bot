"""
Script para parchar main.py y agregar manejo robusto de errores A1111
"""
import sys
from pathlib import Path

# Leer el archivo
main_py = Path("src/main.py")
content = main_py.read_text(encoding="utf-8")

# Patch 1: Agregar None check en are_settings_compliant
old_func = """def are_settings_compliant(settings: dict, preset: Preset) -> bool:
    if settings.get("steps") not in preset.steps:"""

new_func = """def are_settings_compliant(settings: dict, preset: Preset) -> bool:
    # Si no hay preset (sin conexión a A1111), no podemos validar
    if preset is None:
        return False
    if settings.get("steps") not in preset.steps:"""

content = content.replace(old_func, new_func)

# Patch 2: Agregar try-except en settings_cmd
old_settings = """async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    s = load_user_settings(user_id)
    model_name = await get_current_model()
    preset = get_preset_for_model(model_name)
    is_compliant = are_settings_compliant(s, preset)
    await update.message.reply_text(settings_summary(s), reply_markup=main_menu_keyboard(s, is_compliant))"""

new_settings = """async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    s = load_user_settings(user_id)
    try:
        model_name = await get_current_model()
        preset = get_preset_for_model(model_name)
    except Exception as e:
        logging.warning(f"A1111 offline: {e}")
        model_name = None
"""
Script para parchar main.py y agregar manejo robusto de errores A1111
"""
import sys
from pathlib import Path

# Leer el archivo
main_py = Path("src/main.py")
content = main_py.read_text(encoding="utf-8")

# Patch 1: Agregar None check en are_settings_compliant
old_func = """def are_settings_compliant(settings: dict, preset: Preset) -> bool:
    if settings.get("steps") not in preset.steps:"""

new_func = """def are_settings_compliant(settings: dict, preset: Preset) -> bool:
    # Si no hay preset (sin conexión a A1111), no podemos validar
    if preset is None:
        return False
    if settings.get("steps") not in preset.steps:"""

content = content.replace(old_func, new_func)

# Patch 2: Agregar try-except en settings_cmd
old_settings = """async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    s = load_user_settings(user_id)
    model_name = await get_current_model()
    preset = get_preset_for_model(model_name)
    is_compliant = are_settings_compliant(s, preset)
    await update.message.reply_text(settings_summary(s), reply_markup=main_menu_keyboard(s, is_compliant))"""

new_settings = """async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    await update.message.reply_text(settings_summary(s), reply_markup=main_menu_keyboard(s, is_compliant))"""

content = content.replace(old_settings, new_settings)

# Escribir el archivo patcheado
main_py.write_text(content, encoding="utf-8")
print("OK Patch aplicado exitosamente!")
print("- Agregado None check en are_settings_compliant")
print("- Agregado try-except en settings_cmd para manejo A1111 offline")
