#!/usr/bin/env python3
"""
Quick test script to verify resource keyword parsing works correctly.
This tests the PromptGenerator.generate() method to ensure it creates
the {option1|option2|option3} format like the old bot.
"""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from utils.prompt_generator import prompt_generator

def test_parsing():
    """Test that resource keywords are parsed correctly"""
    
    print("Testing Resource Keyword Parsing")
    print("=" * 60)
    
    test_cases = [
        "f_anime in a beautiful garden",
        "m_anime warrior with r_action pose",
        "f_anime with r_color hair in r_place",
        "a beautiful landscape",  # No keywords
        "r_color sunset over r_place with r_light",
    ]
    
    for test_input in test_cases:
        result = prompt_generator.generate(test_input)
        print(f"\nInput:  {test_input}")
        print(f"Output: {result[:150]}{'...' if len(result) > 150 else ''}")
        
        # Verify format if keywords present
        has_keywords = any(kw in test_input for kw in ['f_anime', 'm_anime', 'r_color', 'r_place', 'r_action', 'r_light', 'r_angle', 'r_artist', 'r_style', 'r_object'])
        
        if has_keywords:
            # Should contain {option1|option2|...} format
            if "{" in result and "|" in result and "}" in result:
                print("✅ PASS: Contains A1111 choice format {option1|option2|...}")
            else:
                print("❌ FAIL: Does NOT contain A1111 choice format")
        else:
            # Should remain unchanged
            if result == test_input:
                print("✅ PASS: No keywords, unchanged")
            else:
                print("❌ FAIL: Changed when it shouldn't")
    
    print("\n" + "=" * 60)
    print("Testing complete!")

if __name__ == "__main__":
    test_parsing()
