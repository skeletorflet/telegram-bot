import sys
import os
import random

# Add the current directory to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.prompt_generator import PromptGenerator

def test_limit():
    # Create a dummy resource file for testing
    os.makedirs("resources", exist_ok=True)
    with open("resources/r_test.txt", "w", encoding="utf-8") as f:
        # Write 30 lines
        for i in range(30):
            f.write(f"item{i}\n")
            
    # Initialize generator
    pg = PromptGenerator()
    
    # Manually inject the test resource to avoid reloading if it wasn't picked up
    pg.replacements["r_test"] = [f"item{i}" for i in range(30)]
    
    # Generate a prompt using the test resource
    template = "test {r_test}"
    result = pg.generate(template)
    
    print(f"Result: {result}")
    
    # Extract the options from the result
    # Format is {itemX|itemY|...}
    if result.startswith("test {") and result.endswith("}"):
        content = result[6:-1] # Remove "test {" and "}"
        options = content.split("|")
        print(f"Number of options: {len(options)}")
        
        if len(options) <= 20 and len(options) > 5:
             print("SUCCESS: Limit is greater than 5 and <= 20")
        elif len(options) == 5:
             print("FAILURE: Limit is still 5")
        else:
             print(f"FAILURE: Unexpected number of options: {len(options)}")
    else:
        print("FAILURE: Unexpected format")

    # Clean up
    try:
        os.remove("resources/r_test.txt")
    except:
        pass

if __name__ == "__main__":
    test_limit()
