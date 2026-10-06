# Structure from Motion Reading List

A curated, roughly accessible-to-rigorous reading list on Structure from Motion (SfM) and bundle adjustment, put together after debugging a folded/collapsed reconstruction in the multibanded pipeline (see `multibanded_orthomosaic_alignment.md`). Notes below tie each item back to concepts that came up during that debugging session.

## Start here (practical, free, well-taught)

- **Cyrill Stachniss — Photogrammetry I & II** (free YouTube lecture series + slides, Univ. of Bonn). The best systematic, practitioner-oriented walkthrough of camera models, bundle adjustment, and orientation available for free. Directly covers the align/optimize distinction that came up while debugging `uvvis-front`'s folded reconstruction.
- **COLMAP documentation** + Schönberger & Frahm, *"Structure-from-Motion Revisited"* (CVPR 2016). COLMAP is an open-source incremental SfM pipeline with roughly the same architecture as Metashape (feature matching -> incremental registration/chaining -> bundle-adjustment refinement), but its docs and paper actually explain each stage in prose. Reading how COLMAP describes "incremental registration" vs "bundle adjustment" makes Metashape's `alignCameras`/`optimizeCameras` split much clearer.

## Foundational (why "optimize" is a local refinement, not a re-search)

- Hartley & Zisserman, *Multiple View Geometry in Computer Vision* — the classic textbook. The bundle adjustment and camera model chapters are the rigorous version of the "optimize is local refinement" explanation.
- Triggs, McLauchlan, Hartley, Fitzgibbon, *"Bundle Adjustment -- A Modern Synthesis"* (2000) -- the canonical paper on bundle adjustment as nonlinear least-squares. This is the paper that explains why it's a local, Jacobian-based correction from a starting estimate, not a global search -- directly relevant to why `Tools > Optimize Cameras` alone couldn't unfold an already-folded `uvvis-front` reconstruction, while `Tools > Align Photos` with "Reset current alignment" (i.e. `chunk.alignCameras(reset_alignment=True)`) could.

## Incremental SfM, and why long/weak-texture sequences fold or drift

- Snavely, Seitz, Szeliski, *"Photo Tourism"* (SIGGRAPH 2006) -- the original incremental SfM/"Bundler" paper, adding one image to the chain at a time. This is the architecture pattern behind the folding failure mode seen in `DP2_frontuvvis`.
- The COLMAP paper above also directly discusses drift accumulation and next-best-view selection in incremental reconstruction -- relevant to why a long scanning capture with weak texture (like the UV band on a long panel) can lose the thread partway through and fold back on itself.
- Worth knowing as a contrast: *global* SfM methods (e.g. Theia, OpenMVG's global pipeline) average constraints across all image pairs simultaneously instead of chaining incrementally, specifically to avoid this kind of drift/fold. Not something Metashape exposes, but useful for understanding the tradeoff space.

## Doming -- directly relevant to this codebase

- James & Robson, *"Mitigating systematic error in topographic models derived from UAV and ground-based image networks"* (Earth Surface Processes and Landforms, 2014). This is the paper on the doming effect in self-calibrated SfM with weakly-convergent image geometry -- exactly the phenomenon `multibanded_boards.py`'s calibration-sharing (`MetashapeTask_CopyCalibration`, `calibration_mode="reduced"`/`"fixed"`) was built to avoid.

## One practical, tool-adjacent read

- The **Agisoft Metashape User Manual PDF** (not the Python API reference -- the actual user manual) has noticeably better prose on workflow concepts than the API docs, even though it's still light on the "why."
