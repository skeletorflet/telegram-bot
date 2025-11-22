import random
import re
from pathlib import Path
from typing import Dict, List

class PromptGenerator:
    """Advanced prompt generator with resource files and templates"""
    
    def __init__(self, resources_dir: str = "resources"):
        self.resources_dir = Path(resources_dir)
        self.replacements = self._load_resources()
    
    def _load_resources(self) -> Dict[str, List[str]]:
        """Load resource files for prompt generation"""
        replacements = {}
        resource_files = {
            "r_color": "r_color.txt",
            "r_artist": "r_artist.txt", 
            "r_place": "r_place.txt",
            "r_style": "r_style.txt",
            "r_action": "r_action.txt",
            "r_object": "r_object.txt",
            "f_anime": "f_anime.txt",
            "m_anime": "m_anime.txt",
            "r_light": "r_light.txt",
            "r_angle": "r_angle.txt",
        }
        
        for key, filename in resource_files.items():
            file_path = self.resources_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8-sig") as f:
                        replacements[key] = [line.strip() for line in f if line.strip()]
                except Exception:
                    replacements[key] = [f"!{key.upper()}!"]
            else:
                # Default values if file doesn't exist
                replacements[key] = self._get_default_values(key)
        
        return replacements
    
    def _get_default_values(self, key: str) -> List[str]:
        """Get default values for resource keys"""
        defaults = {
            "r_color": ["vibrant", "pastel", "monochrome", "colorful", "muted"],
            "r_artist": ["artgerm", "greg rutkowski", "makoto shinkai", "studio ghibli"],
            "r_place": ["forest", "city", "beach", "mountain", "space"],
            "r_style": ["realistic", "anime", "cartoon", "painting", "digital art"],
            "r_action": ["standing", "sitting", "running", "jumping", "dancing"],
            "r_object": ["sword", "book", "flower", "crown", "wand"],
            "f_anime": ["cute", "beautiful", "kawaii", "moe", "elegant"],
            "m_anime": ["handsome", "cool", "strong", "mysterious", "brave"],
            "r_light": ["soft lighting", "dramatic lighting", "golden hour", "neon lights"],
            "r_angle": ["front view", "side view", "back view", "aerial view", "close-up"],
        }
        return defaults.get(key, [f"!{key.upper()}!"])
    
    def generate(self, template: str) -> str:
        """Generate enhanced prompt from template using A1111 choice syntax"""
        if not template:
            return template
            
        # Pattern to match resource keys
        pattern = re.compile(r"\b(r_color|r_artist|r_place|r_style|r_action|r_object|f_anime|m_anime|r_light|r_angle)\b")
        
        def replace_match(match):
            key = match.group(1)
            values = self.replacements.get(key, [f"!{key.upper()}!"])
            # Create A1111 choice format: {option1|option2|option3}
            formatted_values = "|".join(values)
            return f"{{{formatted_values}}}"
        
        # Replace all occurrences
        enhanced_template = pattern.sub(replace_match, template)
        return enhanced_template
    
    def enhance_prompt(self, prompt: str, style: str = "general") -> str:
        """Enhance prompt with quality modifiers"""
        quality_modifiers = {
            "general": "masterpiece, best quality, amazing quality,",
            "anime": "masterpiece, best quality, anime style,",
            "realistic": "masterpiece, best quality, photorealistic,",
            "artistic": "masterpiece, best quality, artistic,",
        }
        
        prefix = quality_modifiers.get(style, quality_modifiers["general"])
        
        # Add common enhancements based on content
        enhancements = []
        
        if "portrait" in prompt.lower() or "face" in prompt.lower():
            enhancements.append("detailed face, beautiful eyes")
        
        if "full body" in prompt.lower() or "character" in prompt.lower():
            enhancements.append("full body, detailed clothing")
        
        if "landscape" in prompt.lower() or "scene" in prompt.lower():
            enhancements.append("detailed background, atmospheric")
        
        enhanced = f"{prefix} {prompt}"
        if enhancements:
            enhanced += ", " + ", ".join(enhancements)
        
        return enhanced

# Global instance for easy access
prompt_generator = PromptGenerator()