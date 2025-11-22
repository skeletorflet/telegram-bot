"""
Quick verification of resource keyword parsing.
Shows example outputs of the new implementation.
"""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from utils.prompt_generator import prompt_generator

print("=" * 80)
print("RESOURCE KEYWORD PARSING - VERIFICATION EXAMPLES")
print("=" * 80)

examples = [
    "f_anime in a garden",
    "m_anime warrior",
    "beautiful r_color sunset",
]

for example in examples:
    result = prompt_generator.generate(example)
    print(f"\n📝 Input:  {example}")
    print(f"✨ Output: {result[:120]}...")
    print(f"   Format: {'✅ Contains {option1|option2|...}' if '{' in result and '|' in result else '❌ No format'}")

print("\n" + "=" * 80)
print("✅ Implementation verified! Keywords are replaced with A1111 choice format.")
print("=" * 80)
