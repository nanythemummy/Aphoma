# Camera Calibration from a Checkerboard in Metashape

Metashape doesn't have a dedicated "detect checkerboard corners" tool the way OpenCV does. Its calibration model is solved via self-calibration during bundle adjustment — you get a good calibration by photographing a checkerboard (or any flat, well-textured target) from many varied angles and letting Metashape's normal alignment+optimization solve the lens model, because that geometry is well-constrained (lots of convergence angles, near and far, corner-to-corner coverage).

This is the more reliable version of what `optimize_cameras()` in `photogrammetry/ModelHelpers.py` does with `calibration_mode="full"` — the difference is that a dedicated checkerboard shoot gives the bundle adjustment much better-conditioned geometry than a near-planar object, which is exactly why the multibanded boards are prone to "doming" when self-calibrated on their own.

## Walkthrough

1. **Shoot the calibration set.** Print or mount a flat checkerboard/calibration target. With the *exact* camera body, lens, focal length (if zoom, tape it down), and focus distance you use in production (calibration is invalid if focus/zoom changes — refocusing shifts the internal lens elements and thus the calibration), take 30-60+ photos of the target:
   - Varying angle/tilt substantially (not just straight-on shots — you need convergence angles for the lens distortion to be well-constrained)
   - Varying distance (near and far)
   - Covering all four corners and edges of the frame, not just the center, in different shots
   - Some rotated 90° (portrait vs landscape) if you want b1/b2 (affine/skew) well-constrained too

2. **New chunk in Metashape.** `Workflow > Add Photos...` (or `Add Folder`) into a fresh chunk dedicated to this calibration set — don't mix it into a production chunk.

3. **Align Photos.** `Workflow > Align Photos...`. Use Highest or High accuracy, generic preselection on, reference preselection off (no meaningful GPS). Key point/tie point limits high (e.g. 40,000/4,000) since you want lots of correspondences across the checkerboard's regular texture.

4. **Optimize Cameras with full self-calibration.** `Tools > Optimize Cameras...` (this is the UI front-end for what the code calls via `chunk.optimizeCameras()`). Check **all** the parameter boxes: f, cx, cy, k1, k2, k3, k4, p1, p2, p3, b1, b2. Since this photoset has strong, varied geometry (unlike the flat multibanded boards), this full fit should converge cleanly without doming.

5. **Inspect the result.** `Tools > Camera Calibration...`. Select the sensor. You'll see the "Initial" (from EXIF/rough) vs "Adjusted" (solved) tabs with f, cx, cy, and distortion coefficients. Check that reprojection error (visible in the Reference panel / `Tools > Optimize Cameras` output, or per-tie-point residuals) is low and evenly distributed — no residual pattern that looks like uncorrected distortion.

6. **Save the calibration.** Still in the Camera Calibration dialog, there's a save icon/button to export the adjusted calibration to an `.xml` file. Save it somewhere you'll reuse it.

7. **Apply it to production chunks.** In your real project, open `Tools > Camera Calibration...` for the matching sensor, use the load button to import that `.xml`, and check **"Fix calibration"** so subsequent alignment/optimization treats it as fixed rather than re-solving it. This is the UI equivalent of what `MetashapeTask_CopyCalibration`/`copy_calibration()` already does programmatically between chunks in the same project — the difference is this gives you a calibration derived from a properly-constrained checkerboard shoot rather than from one of your own (weakly-constrained, planar) multibanded chunks.

## Legacy alternative

Agisoft used to ship a separate standalone tool called **Agisoft Lens** specifically for checkerboard-pattern calibration, which exported an XML directly loadable into this same Camera Calibration dialog. Current availability/maintenance status is unconfirmed — worth checking Agisoft's site if a purpose-built checkerboard-corner detector is preferred over the self-calibration-via-bundle-adjustment approach above, but the workflow above is the standard, fully-supported way to do it in current Metashape.
