import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))

from pressets.pressets import PRESETS

print("Keys in PRESETS:")
for key in PRESETS:
    print(f"- {key}")

if "cyberrealisticpony" in PRESETS:
    print("cyberrealisticpony FOUND")
else:
    print("cyberrealisticpony NOT FOUND")
