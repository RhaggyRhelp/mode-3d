"""Benchmark 4096 resolution inference on RTX 4070 Ti SUPER 16GB."""
import time
import torch
import cv2
import numpy as np
from pathlib import Path
from moge.model import import_model_class_by_version

REPO_ROOT = Path(__file__).resolve().parents[1]
img_candidates = [
    REPO_ROOT / "tests" / "test_data" / "sample.jpg",
    REPO_ROOT.parent / "MoGe" / "example_images" / "01_HouseIndoor.jpg",
    Path.home() / "MoGe" / "example_images" / "01_HouseIndoor.jpg",
]
img_path = next((p for p in img_candidates if p.exists()), img_candidates[0])

bgr = cv2.imread(str(img_path))
rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
h0, w0 = rgb.shape[:2]

# Scale long edge to 4096
target_max = 4096
scale = target_max / max(h0, w0)
new_w = int(round(w0 * scale))
new_h = int(round(h0 * scale))
rgb_4k = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
h, w = rgb_4k.shape[:2]
total_pixels = h * w

print(f"=== 4096 BENCHMARK ===")
print(f"Input image shape: {w}x{h} ({total_pixels:,} pixels)")
device_name = torch.cuda.get_device_name(0)
total_vram = torch.cuda.get_device_properties(0).total_memory / 1e9
print(f"GPU: {device_name} ({total_vram:.2f} GB VRAM)")

def test_model(version, variant, refine_steps, res_level=9):
    print(f"\n--- Testing: MoGe-{version} ({variant}), refine_steps={refine_steps}, res_level={res_level} ---")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    
    t0 = time.perf_counter()
    try:
        cls = import_model_class_by_version(version)
        model_name = "Ruicheng/moge-3-vitg" if variant == "vitg" else "Ruicheng/moge-3-vitl"
        print(f"Loading {model_name}...")
        model = cls.from_pretrained(model_name).cuda().eval()
        t_load = time.perf_counter() - t0
        vram_load = torch.cuda.memory_allocated() / 1e9
        print(f"Model loaded in {t_load:.2f}s (VRAM baseline: {vram_load:.2f} GB)")

        t_in = torch.tensor(rgb_4k, dtype=torch.float32, device="cuda").permute(2, 0, 1) / 255.0
        
        t_infer_start = time.perf_counter()
        with torch.no_grad():
            out = model.infer(
                t_in,
                resolution_level=res_level,
                refine_steps=refine_steps,
                use_fp16=True
            )
        t_infer = time.perf_counter() - t_infer_start
        peak_vram = torch.cuda.max_memory_allocated() / 1e9
        print(f"SUCCESS! Inference completed in {t_infer:.2f}s")
        print(f"Peak VRAM used: {peak_vram:.2f} GB / {total_vram:.2f} GB ({peak_vram/total_vram*100:.1f}%)")
        print(f"Output depth shape: {out['depth'].shape}")
        
        # Cleanup
        del model
        del out
        del t_in
        torch.cuda.empty_cache()
        return True, peak_vram, t_infer
    except torch.cuda.OutOfMemoryError as oom:
        print(f"FAILED: CUDA OutOfMemoryError!")
        print(oom)
        torch.cuda.empty_cache()
        return False, None, None
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        torch.cuda.empty_cache()
        return False, None, None

# Test 1: ViT-L with refine=2 (standard)
success_l, vram_l, t_l = test_model("v3", "vitl", refine_steps=2)

# Test 2: ViT-G with refine=2
success_g, vram_g, t_g = test_model("v3", "vitg", refine_steps=2)

# Test 3: If ViT-G succeeded, test with refine=7 (user requested)
if success_g:
    success_g7, vram_g7, t_g7 = test_model("v3", "vitg", refine_steps=7)
