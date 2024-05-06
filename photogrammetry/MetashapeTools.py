import os
import Metashape

def build_basic_model(photodir, outputdir, projectname, config):
    """Builds a model using the photos in the directory specified."""
    #Open a new document
    doc = Metashape.Document()
    try:
        doc.save(path = os.path.join(outputdir,projectname+".psx"))
        #add  a new chunk
        chunk = doc.addChunk()
        #add the photos in the specified directory to that chunk.
        images = os.listdir(photodir)
        for i in images:
            if os.path.splitext(i)[1] in [".jpg", ".tiff",".tif"]:
                chunk.addPhotos(os.path.join(photodir,i))
        doc.save()
        #Add Masks if needed.
        maskKeypoints=False
        if config["mask_path"]:
            mp = os.path.join(config["mask_path"])
            ext = config["mask_ext"]
            masktemplate = f"{mp}/{{filename}}.{ext}"
            chunk.generateMasks(masktemplate,Metashape.MaskingMode.MaskingModeFile)
            maskKeypoints=True
            doc.save()
        #match photos/align photos--for now the default settings are fine.
        chunk.matchPhotos(filter_mask = maskKeypoints, generic_preselection=False)
        chunk.alignCameras()
        doc.save()
    except Exception as e:
        print(e.args)