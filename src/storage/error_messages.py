"""
Storage for error message IDs to enable cleanup on bot restart
"""
import json
from pathlib import Path
from typing import Set
import logging

ERROR_MESSAGES_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "error_messages.json"

def load_error_messages() -> dict:
    """Load stored error message IDs grouped by chat_id"""
    if ERROR_MESSAGES_FILE.exists():
        try:
            with open(ERROR_MESSAGES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Convert string keys to int and values to sets
                return {int(k): set(v) for k, v in data.items()}
        except Exception as e:
            logging.error(f"Error loading error messages: {e}")
            return {}
    return {}

def save_error_messages(error_msgs: dict) -> None:
    """Save error message IDs to file"""
    try:
        ERROR_MESSAGES_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Convert integer keys to strings and sets to lists for JSON
        data = {str(k): list(v) for k, v in error_msgs.items()}
        with open(ERROR_MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        logging.error(f"Error saving error messages: {e}")

def add_error_message(chat_id: int, message_id: int) -> None:
    """Add an error message ID to the tracking system"""
    error_msgs = load_error_messages()
    if chat_id not in error_msgs:
        error_msgs[chat_id] = set()
    error_msgs[chat_id].add(message_id)
    save_error_messages(error_msgs)

def remove_error_message(chat_id: int, message_id: int) -> None:
    """Remove an error message ID from tracking (after deletion)"""
    error_msgs = load_error_messages()
    if chat_id in error_msgs and message_id in error_msgs[chat_id]:
        error_msgs[chat_id].remove(message_id)
        # Remove chat if no more error messages
        if not error_msgs[chat_id]:
            del error_msgs[chat_id]
        save_error_messages(error_msgs)

def get_error_messages_for_chat(chat_id: int) -> Set[int]:
    """Get all error message IDs for a specific chat"""
    error_msgs = load_error_messages()
    return error_msgs.get(chat_id, set())

def clear_all_error_messages() -> None:
    """Clear all tracked error messages"""
    save_error_messages({})
