@app.post("/pano")
async def pano(
    image: UploadFile = File(..., description="equirectangular 360 image (2:1)"),
    n_yaw: int = Form(8),
    include_poles: bool = Form(True),
    face_size: int = Form(1536),
    model_version: str = Form("v3"),
    variant: str = Form("vitl"),
    resolution_level: str = Form("High"),
    refine_steps: int = Form(2),
    apply_mask: bool = Form(False),
    remove_edges: bool = Form(True),
    face_cap: int = Form(400000),
):
    """Full-room scan: equirect -> tangent faces @forced 90deg -> loop-closed
    scale solve -> merged cloud in pano frame (face0 identity) + camera rig.
    Returns pano.npz with FLAT arrays (points/colors/normals/depths/face_id)."""
    from shared.pano import (extract_face, tangent_frame, boundary_columns,
                             pole_wedge_mask, solve_scales,
                             apply_face_transform, side_wedge_mask, pole_cap_mask)
    from shared.zoom import rotate_normals
    t_all = time.perf_counter()
    try:
        n_yaw = int(n_yaw)
        if n_yaw not in (4, 6, 8):
            return JSONResponse({"error": "n_yaw must be 4/6/8 (8 recommended: 50% overlap)"}, status_code=400)
        face_size = max(512, min(int(face_size), MAX_INFER_DIM))
        face_cap = max(50000, min(int(face_cap), 2000000))
        model_version = str(model_version).lower().strip()
        variant = str(variant).lower().strip() or "vitl"
        if (model_version, variant) not in PRETRAINED:
            return JSONResponse({"error": "unknown model/variant"}, status_code=400)
        level_int = clamp_resolution(resolution_level)

        raw = await image.read()
        if not raw:
            return JSONResponse({"error": "empty image upload"}, status_code=400)
        from PIL import Image as PILImage
        PILImage.MAX_IMAGE_PIXELS = None
        try:
            equi = np.asarray(PILImage.open(io.BytesIO(raw)).convert("RGB"))
        except Exception as e:
            return JSONResponse({"error": f"could not decode equirect: {e}"}, status_code=400)
        H0, W0 = equi.shape[:2]
        if not 1.8 < W0 / max(H0, 1) < 2.2:
            return JSONResponse(
                {"error": f"not equirectangular (need ~2:1, got {W0}x{H0})"}, status_code=400)

        model = get_model(model_version, variant)
        yaw_step = 360.0 / n_yaw
        side_fov = 98.0 if n_yaw == 4 else 90.0
        specs = [(k * yaw_step, 0.0) for k in range(n_yaw)]
        if bool(include_poles):
            specs += [(0.0, 90.0), (0.0, -90.0)]  # ceiling, floor (pitch>0 = up)
        F = len(specs)
        t_inf = time.perf_counter()
        faces = []
        for fi, (yw, pt) in enumerate(specs):
            face_fov = side_fov if pt == 0.0 else 90.0
            frgb = extract_face(equi, yw, pt, fov_deg=face_fov, size=face_size)
            out = run_infer(model, model_version, frgb, level_int,
                            max(0, min(int(refine_steps), 7)), face_fov)
            dep = np.asarray(out["depth"], dtype=np.float64)
            _n = out.get("normal")
            nrm = np.asarray(_n, dtype=np.float64) if _n is not None else np.zeros(dep.shape + (3,))
            msk = np.asarray(out.get("mask", np.ones(dep.shape, bool))).astype(bool)
            pts = np.asarray(out["points"], dtype=np.float64)
            Kf = np.asarray(out["intrinsics"], dtype=np.float64)
            R = tangent_frame(yw, pt)
            mf = finalize_mask(pts, dep, nrm, msk, False, bool(apply_mask), bool(remove_edges))
            faces.append({"yaw": yw, "pitch": pt, "R": R, "rgb": frgb,
                          "depth": dep, "normal": nrm, "mask": mf, "points": pts,
                          "K": Kf, "fov": face_fov})
            print(f"[daemon] pano face {fi + 1}/{F} yaw={yw:.0f} pitch={pt:.0f} fov={face_fov:.0f} "
                  f"valid={mf.sum()}", flush=True)
        t_inf = time.perf_counter() - t_inf

        # --- affine solve ANCHORED ON WHAT RENDERS: PAIRED boundary samples.
        # Medians agreed (post 0.4%) while handoffs still gapped 30%: the two
        # sides of a seam contain different content mixes (wall vs doorway),
        # so unpaired medians compare different things. Paired samples on
        # shared rays + trimmed joint (scale, shift) fit both sides at once.
        # Poles stay scale-only (rings are unpaired by nature) fit to fixed sides.
        from shared.pano import solve_affine
        from shared.tta import depth_to_points
        fh, fw = faces[0]["depth"].shape
        ci, cj = boundary_columns(n_yaw, side_fov, fw)
        # length-match: both span the same yaw range monotonically
        L = min(len(ci), len(cj))
        ci, cj = ci[:L], cj[:L]
        row_stride = max(1, fh // 256)
        pairs = []
        pre_res = []
        for k in range(n_yaw):
            d1, m1 = faces[k]["depth"], faces[k]["mask"]
            d2, m2 = faces[(k + 1) % n_yaw]["depth"], faces[(k + 1) % n_yaw]["mask"]
            if L == 0:
                continue
            a = d1[::row_stride][:, ci]
            b = d2[::row_stride][:, cj]
            ma = m1[::row_stride][:, ci] & np.isfinite(a)
            mb = m2[::row_stride][:, cj] & np.isfinite(b)
            ok = ma & mb
            if int(ok.sum()) < 500:
                continue
            pairs.append((k, (k + 1) % n_yaw, a[ok], b[ok]))
            pre_res.append(float(np.median(np.abs(a[ok] - b[ok]) / np.maximum(a[ok], 1e-3))))
        # scalar anchor first (median ratios; absolute level lives here), then
        # anchored affine for boundary agreement (shifts absorb offsets).
        from shared.pano import solve_scales
        # Reciprocal depth ratio: larger predicted depth requires smaller scale (s_i / s_j = d_j / d_i)
        _terms = [(i, j, float(np.log(max(np.median(b), 1e-9) / max(np.median(a), 1e-9))), 1.0)
                  for i, j, a, b in pairs]
        s_side, t_side, pair_post = solve_affine(
            pairs, n_yaw, s_ref=solve_scales(_terms, n_yaw) if _terms else None)
        s8 = np.asarray(s_side, dtype=np.float64)
        pole_scales = []
        for pi, side in ((n_yaw, "top"), (n_yaw + 1, "bottom")):
            if not bool(include_poles):
                break
            pd = faces[pi]["depth"]
            pm = faces[pi]["mask"]
            cand = []
            for k in range(n_yaw):
                wm = pole_wedge_mask(fh, fw, faces[pi]["R"], k * yaw_step, half_width_deg=(360.0 / n_yaw) * 0.6)
                pv = pm & np.isfinite(pd) & wm
                sd = faces[k]["depth"]
                sm = faces[k]["mask"]
                edge_rows = np.zeros(sm.shape, bool)
                if side == "top":
                    edge_rows[:40, :] = True
                else:
                    edge_rows[-40:, :] = True
                band = sm & np.isfinite(sd) & edge_rows
                if int(pv.sum()) < 2000 or int(band.sum()) < 2000:
                    continue
                # Reciprocal: s_pole = s_side * (sd / pd)
                lr = float(np.log(max(np.median(sd[band]), 1e-9) / max(np.median(pd[pv]), 1e-9)))
                cand.append(float(s8[k]) * math.exp(lr))
            pole_scales.append(float(np.median(cand)) if len(cand) >= 3 else 1.0)
        if bool(include_poles):
            scales = np.concatenate([s8, np.asarray(pole_scales)]).tolist()
        else:
            scales = s8.tolist()
        shifts = np.concatenate([np.asarray(t_side, dtype=np.float64),
                                 np.zeros(max(F - n_yaw, 0))]).tolist()
        # post-fit residual in the SAME units as pre (median paired |rel| diff):
        # directly comparable pair by pair.
        post_med = float(np.nanmedian(pair_post)) if pair_post else 0.0
        post_rms = post_med
        pre_med = float(np.median(np.abs(pre_res))) if pre_res else 0.0

        # --- exclusive display wedges (no rendered overlap -> no doubling).
        # Solve used the FULL faces; output keeps each face's exclusive sector:
        # sides keep |yaw_rel| <= spacing/2, poles keep the polar cap. Where one
        # cloud ends, the neighbor picks up along shared boundary rays.
        for fi, fc in enumerate(faces):
            if fi < n_yaw:
                fc["wedge"] = side_wedge_mask(fh, fw, n_yaw, fov_deg=side_fov)
            else:
                is_top = bool(fc["pitch"] and fc["pitch"] > 0)
                fc["wedge"] = pole_cap_mask(fh, fw, fc["R"], is_top, fov_deg=fc.get("fov", 90.0))

        # boundary seam stat: adjacent kept columns across every side pair,
        # with the affine correction applied (the honest handoff number).
        def _corr(fc, fi):
            s = float(scales[fi])
            t = float(shifts[fi]) if fi < len(shifts) else 0.0
            d = np.asarray(fc["depth"], dtype=np.float64)
            out = np.where(np.isfinite(d), d * s + t, np.inf)
            return np.where(out > 0.01, out, np.inf)

        seam_vals = []
        for k in range(n_yaw):
            d1 = _corr(faces[k], k)
            d2 = _corr(faces[(k + 1) % n_yaw], (k + 1) % n_yaw)
            m1 = faces[k]["mask"] & faces[k]["wedge"]
            m2 = faces[(k + 1) % n_yaw]["mask"] & faces[(k + 1) % n_yaw]["wedge"]
            cols1 = np.nonzero(faces[k]["wedge"][fh // 2])[0]
            cols2 = np.nonzero(faces[(k + 1) % n_yaw]["wedge"][fh // 2])[0]
            if len(cols1) == 0 or len(cols2) == 0:
                continue
            c1, c2 = cols1[-1], cols2[0]
            a = d1[:, c1]
            b = d2[:, c2]
            ok = m1[:, c1] & m2[:, c2] & np.isfinite(a) & np.isfinite(b) & (a > 0.05) & (b > 0.05)
            if int(ok.sum()) > 200:
                seam_vals.append(float(np.median(np.abs(np.log(a[ok] / np.maximum(b[ok], 1e-9))))))
        seam_med = float(np.median(seam_vals)) if seam_vals else float("nan")

        # --- merge into pano frame (face0 identity), stride-capped per face ---
        # Affine-corrected depths are REPROJECTED (a shift is not a 3D scale),
        # using each face's own MoGe intrinsics.
        P_all, C_all, N_all, D_all, F_all = [], [], [], [], []
        counts = []
        for fi, fc in enumerate(faces):
            R, s = fc["R"], float(scales[fi])
            t = float(shifts[fi]) if fi < len(shifts) else 0.0
            raw = np.asarray(fc["depth"], dtype=np.float64)
            dep = np.where(np.isfinite(raw), raw * s + t, np.inf)
            dep = np.where(dep > 0.01, dep, np.inf)
            fin = np.isfinite(dep)
            fin3 = np.repeat(fin[:, :, None], 3, axis=2)
            pts_face = depth_to_points(np.where(fin, dep, 0.0), fc["K"])
            pts = apply_face_transform(np.where(fin3, pts_face, 0.0), R, 1.0)
            pts[~fin3] = np.inf
            nrm = rotate_normals(fc["normal"], R)
            valid = fc["mask"] & fc["wedge"] & fin & np.all(np.isfinite(pts), axis=-1)
            ys, xs = np.nonzero(valid)
            if ys.shape[0] > face_cap:
                st = int(math.ceil(ys.shape[0] / face_cap))
                ys, xs = ys[::st], xs[::st]
            P_all.append(pts[ys, xs].astype(np.float32))
            C_all.append(fc["rgb"][ys, xs])
            N_all.append(nrm[ys, xs].astype(np.float32))
            D_all.append(dep[ys, xs].astype(np.float32))
            F_all.append(np.full(ys.shape[0], fi, dtype=np.int32))
            counts.append(int(ys.shape[0]))
        points = np.concatenate(P_all, axis=0)
        colors = np.concatenate(C_all, axis=0)
        normals = np.concatenate(N_all, axis=0)
        depths = np.concatenate(D_all, axis=0)
        face_id = np.concatenate(F_all, axis=0)

        buf = io.BytesIO()
        np.savez(
            buf,
            points=np.ascontiguousarray(points),
            colors=np.ascontiguousarray(colors),
            normals=np.ascontiguousarray(normals),
            depths=np.ascontiguousarray(depths),
            face_id=np.ascontiguousarray(face_id),
            scales=np.ascontiguousarray(np.asarray(scales, dtype=np.float32)),
            shifts=np.ascontiguousarray(np.asarray(shifts, dtype=np.float32)),
            face_yaw=np.asarray([f["yaw"] for f in faces], dtype=np.float32),
            face_pitch=np.asarray([f["pitch"] for f in faces], dtype=np.float32),
            face_counts=np.asarray(counts, dtype=np.int32),
            fov=np.float32(side_fov),
            face_size=np.int32(face_size),
            fx_px=np.float32((face_size / 2.0) / math.tan(math.radians(side_fov / 2.0))),
            n_yaw=np.int32(n_yaw),
            pre_resid=np.float32(pre_med),
            post_resid=np.float32(post_med),
            post_rms=np.float32(post_rms),
            seam_resid=np.float32(seam_med if seam_med == seam_med else -1.0),
        )
        print(f"[daemon] pano {W0}x{H0} -> {F} faces, {points.shape[0]} pts, "
              f"pre={pre_med:.3f} post={post_med:.4f} seam={seam_med:.4f} "
              f"infer={t_inf:.1f}s total={time.perf_counter() - t_all:.1f}s", flush=True)
        return Response(content=buf.getvalue(), media_type="application/x-numpy-archive")
    except Exception as e:  # never crash warm process on bad input
        traceback.print_exc()
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


