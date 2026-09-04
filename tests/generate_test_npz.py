"""Generate test npz for Blender render."""
import cv2
import torch
import numpy as np
from pathlib import Path
from moge.model import import_model_class_by_version

REPO_ROOT = Path(__file__).resolve().parents[1]
out_dir = REPO_ROOT / "tests" / "test_data"
out_dir.mkdir(parents=True, exist_ok=True)
img_candidates = [
    REPO_ROOT / "tests" / "test_data" / "sample.jpg",
    REPO_ROOT.parent / "MoGe" / "example_images" / "01_HouseIndoor.jpg",
    Path.home() / "MoGe" / "example_images" / "01_HouseIndoor.jpg",
]
img_path = next((p for p in img_candidates if p.exists()), img_candidates[0])

bgr = cv2.imread(str(img_path))
rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
rgb_s = cv2.resize(rgb, (800, 533))

cls = import_model_class_by_version("v3")
model = cls.from_pretrained("Ruicheng/moge-3-vitl").cuda().eval()
t_in = torch.tensor(rgb_s, dtype=torch.float32, device="cuda").permute(2, 0, 1) / 255.0

with torch.no_grad():
    out = model.infer(t_in, resolution_level=5, refine_steps=2, use_fp16=True)

np.savez(
    out_dir / "01_HouseIndoor.npz",
    points=out["points"].cpu().numpy().astype(np.float32),
    depth=out["depth"].cpu().numpy().astype(np.float32),
    normal=out["normal"].cpu().numpy().astype(np.float32),
    intrinsics=out["intrinsics"].cpu().numpy().astype(np.float32),
    image=rgb_s
)
print("Saved 01_HouseIndoor.npz successfully!")
