from html import escape as html_escape
from typing import Optional

class FormatText:
    """HTML formatting utilities for Telegram messages"""
    
    @staticmethod
    def bold(text: str) -> str:
        return f"<b>{html_escape(str(text))}</b>"
    
    @staticmethod
    def italic(text: str) -> str:
        return f"<i>{html_escape(str(text))}</i>"
    
    @staticmethod
    def underline(text: str) -> str:
        return f"<u>{html_escape(str(text))}</u>"
    
    @staticmethod
    def strikethrough(text: str) -> str:
        return f"<s>{html_escape(str(text))}</s>"
    
    @staticmethod
    def code(text: str) -> str:
        return f"<code>{html_escape(str(text))}</code>"
    
    @staticmethod
    def pre(text: str) -> str:
        return f"<pre>{html_escape(str(text))}</pre>"
    
    @staticmethod
    def link(text: str, url: str) -> str:
        return f'<a href="{html_escape(url)}">{html_escape(str(text))}</a>'
    
    @staticmethod
    def blockquote(text: str) -> str:
        return f"<blockquote>{html_escape(str(text))}</blockquote>"
    
    @staticmethod
    def linebreak(count: int = 1) -> str:
        return "\n" * count
    
    @staticmethod
    def emoji(text: str, emoji: str) -> str:
        return f"{emoji} {text}"

def escape_html_entities(text: str) -> str:
    """Escape HTML entities in text"""
    return html_escape(text)

def format_queue_status(position: int, total: int, prompt: str) -> str:
    """Format queue status message with emojis"""
    status_emoji = "🔄" if position > 1 else "⚙️"
    return (
        f"{FormatText.bold(FormatText.emoji('Solicitud en cola', status_emoji))}\n"
        f"{FormatText.bold('Posición:')} {position} de {total}\n"
        f"{FormatText.bold('Prompt:')} {FormatText.code(escape_html_entities(prompt[:100]) + '...' if len(prompt) > 100 else prompt)}"
    )

def format_generation_complete(prompt: str, seed: int, settings: dict) -> str:
    """Format generation complete message"""
    return (
        f"{FormatText.bold(FormatText.emoji('✅ Generación completada', '🎨'))}\n"
        f"{FormatText.bold('Prompt:')} {FormatText.code(escape_html_entities(prompt[:150]) + '...' if len(prompt) > 150 else prompt)}\n"
        f"{FormatText.bold('Seed:')} {FormatText.code(str(seed))}"
    )

def format_error_message(error: str) -> str:
    """Format error message with emoji"""
    return f"{FormatText.bold(FormatText.emoji('❌ Error', '⚠️'))}\n{FormatText.code(error)}"

def format_settings_updated(setting_name: str, value: str) -> str:
    """Format settings update confirmation"""
    return f"{FormatText.emoji('✅ Configuración actualizada', '⚙️')} {setting_name}: {FormatText.code(value)}"

def format_welcome_message() -> str:
    """Format welcome message with emojis and instructions"""
    return (
        f"{FormatText.bold(FormatText.emoji('🤖 Bienvenido al Bot de Generación de Imágenes', '🎨'))}\n\n"
        f"{FormatText.bold('Comandos disponibles:')}\n"
        f"• {FormatText.code('/start')} - Mostrar este mensaje\n"
        f"• {FormatText.code('/settings')} - Configurar opciones de generación\n"
        f"• {FormatText.code('/txt2img <prompt>')} - Generar imagen con prompt\n"
        f"• {FormatText.code('<prompt>')} - Generar imagen directamente\n\n"
        f"{FormatText.bold('Características:')}\n"
        f"• {FormatText.emoji('Sistema de cola inteligente', '⏳')}\n"
        f"• {FormatText.emoji('Configuración personalizable', '⚙️')}\n"
        f"• {FormatText.emoji('Soporte para LoRA', '🎯')}\n"
        f"• {FormatText.emoji('Upscale de imágenes', '🔍')}\n"
        f"• {FormatText.emoji('Repetición con diferentes seeds', '🔄')}"
    )