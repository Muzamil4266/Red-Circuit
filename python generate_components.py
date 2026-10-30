import os
import base64

component_folder = r"C:\Shoby deathless laptop folder\Red Circuit Project\Electronic components"
output_file = r"C:\Shoby deathless laptop folder\Red Circuit Project\components_data.py"

print("Scanning and packing component photos into embedded module...")

with open(output_file, "w", encoding="utf-8") as out:
    out.write("# Auto-generated embedded components module\n")
    out.write("EMBEDDED_COMPONENTS = {\n")
    
    if os.path.exists(component_folder):
        count = 0
        for filename in sorted(os.listdir(component_folder)):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
                path = os.path.join(component_folder, filename)
                display_name = os.path.splitext(filename)[0].replace("_", " ")
                try:
                    with open(path, "rb") as img_file:
                        b64_str = base64.b64encode(img_file.read()).decode("utf-8")
                        out.write(f'    "{display_name}": "{b64_str}",\n')
                        count += 1
                except Exception as e:
                    print(f"Skipped {filename}: {e}")
        print(f"Successfully packed {count} photos into components_data.py!")
    else:
        print(f"Error: Could not find folder at {component_folder}")

    out.write("}\n")