import os
import Metashape

def build_basic_model(photodir, outputdir, projectname, config):
    """Builds a model using the photos in the directory specified."""
    #Open a new document
    projectpath = os.path.join(outputdir,projectname+".psx")
    doc = Metashape.Document()
    if os.path.exists(projectpath):
        doc.open(path=projectpath)
    doc.save(path=projectpath)
    #add  a new chunk
    chunk=None
    if len(doc.chunks)==0:
        chunk = doc.addChunk()
    else:
        chunk=doc.chunks[0]
    #add the photos in the specified directory to that chunk.
    images = os.listdir(photodir)
    for i in images:
        if os.path.splitext(i)[1] in [".jpg", ".tiff",".tif"]:
            chunk.addPhotos(os.path.join(photodir,i))
    doc.save()
    #add masks if they exist.
    maskKeypoints=False
    if config["mask_path"]:
        mp = os.path.join(config["mask_path"])
        ext = config["mask_ext"]
        template = f"{mp}{os.sep}{{filename}}.{ext}"
        chunk.generateMasks(template,Metashape.MaskingMode.MaskingModeFile)
        maskKeypoints=True
    chunk.matchPhotos(downscale=0,
                      generic_preselection=True,
                      reference_preselection=True,
                      reference_preselection_mode=Metashape.ReferencePreselectionMode.ReferencePreselectionSource,
                      filter_mask=maskKeypoints,
                      mask_tiepoints=False,
                      filter_stationary_points=True,
                      tiepoint_limit=0,
                      reset_matches=True
    )
    chunk.alignCameras()
    doc.save()

def gradualSelectWorkflow():
    pass