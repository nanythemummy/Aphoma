from pathlib import Path
import sys
import Metashape
import math
parentpath = Path(__file__).parent.parent.absolute()
sys.path.append(str(parentpath))
from tasks.MetashapeTasksSpecial import MetashapeTask_ResizeBoundingBoxFromMarkers
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from util.Configurator import Configurator



def ResizeToMarkers():
    markers = sys.argv[1].split(",")
    print("starting")
    if not len(markers)==4:
        print(f"Length of parameter is {len(markers)} rather than the expected 6 members.")
        return


    doc = Metashape.app.document
    
    chunk = doc.chunk
    projname = Path(doc.path).stem
    outputfolder = Path(doc.path).parent
    print(f"projectname:{projname}, outputfolder:{outputfolder}")
    _= MetashapeFileSingleton.getMetashapeDoc(projname,outputfolder,doc)
    print("Initialized singleton")
    tasklist = []
    tasklist.append(MetashapeTask_ResizeBoundingBoxFromMarkers({"input":"","output":outputfolder,"projectname":projname,"chunkname":chunk.label,"dimensionmarkers":markers}))
    for task in tasklist:
        if task.setup():
            print(f"Executing {task}")
            task.execute()
        else:
            print("Failed because reorient task setup failed.")
        task.exit()
LABEL = "Reize Region to Markers"
Metashape.app.addMenuItem(LABEL, ResizeToMarkers )
print("To execute this script press {}".format(LABEL))