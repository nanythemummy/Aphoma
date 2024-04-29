import os
import Metashape

def build_basic_model(photodir, outputdir, projectname):
    """Builds a model using the photos in the directory specified."""
    #Open a new document
    doc = Metashape.Document()
    doc.save(path = os.path.join(outputdir,projectname+".psx"))
    #add  a new chunk
    chunk = doc.addChunk()
    #add the photos in the specified directory to that chunk.
    images = os.listdir(photodir)
    for i in images:
        if os.path.splitext(i)[1] in [".jpg", ".tiff",".tif"]:
            chunk.addPhotos(os.path.join(photodir,i))
    
    doc.save()
    #match photos/align photos--for now the default settings are fine.
    chunk.matchPhotos(generic_preselection=False)
    chunk.alignCameras()
    doc.save()