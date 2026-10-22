"""Example: use an exported markers.py / markers.json from your own program.

    python use_markers.py path/to/export-folder [image.png]
"""

import importlib.util
import json
import sys
from pathlib import Path

folder = Path(sys.argv[1])

# Option 1: markers.json (any language can read this)
data = json.loads((folder / "markers.json").read_text(encoding="utf-8"))
name_to_id = {name: tag["id"] for name, tag in data["tags"].items()}
print("dictionary:", data["dictionary"], "| tag size:", data["tag_size_mm"], "mm")
print("from markers.json:", name_to_id)

# Option 2: markers.py (copy it next to your code and `import markers`;
# loading it by path here so the example works from anywhere)
spec = importlib.util.spec_from_file_location("markers", folder / "markers.py")
markers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(markers)
print("from markers.py:", markers.MARKERS)

if len(sys.argv) > 2:
    import cv2

    image = cv2.imread(sys.argv[2])
    print("detected:", markers.detect(image))
