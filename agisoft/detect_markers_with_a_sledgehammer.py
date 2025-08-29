from pathlib import Path
import sys
import Metashape
parentpath = Path(__file__).parent.parent.absolute()
sys.path.append(str(parentpath))
from tasks.MetashapeTasksSpecial import MetashapeTask_DetectMarkersFromThresholdedImage
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from util.Configurator import Configurator


def GenerateMarkersFromThresholdedImages():
    threshold = int(sys.argv[1])
    print("Hi.")
    doc = Metashape.app.document
   
    chunk = doc.chunk
    projname = Path(doc.path).stem
    outputfolder = Path(doc.path).parent
    print(f"projectname:{projname}, outputfolder:{outputfolder}")
    _= MetashapeFileSingleton.getMetashapeDoc(projname,outputfolder,doc)
    print("Initialized singleton")
    reorienttask = MetashapeTask_DetectMarkersFromThresholdedImage({"input":"","output":outputfolder,"projectname":projname,"chunkname":chunk.label,"threshold":threshold})
    if reorienttask.setup():
        print("Executing detect markers from thresholded images")
        reorienttask.execute()
    else:
        print("Failed because reorient task setup failed.")
    reorienttask.exit()

LABEL = "Sledgehammer."
Metashape.app.addMenuItem(LABEL, GenerateMarkersFromThresholdedImages)
print("To execute this script press {}".format(LABEL))