from pathlib import Path
import sys
import Metashape
parentpath = Path(__file__).parent.parent.absolute()
sys.path.append(str(parentpath))
from tasks.MetashapeTasksSpecial import MetashapeTask_ResizeBoundingBox
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from util.Configurator import Configurator


def ResizeBoundingBox():
    whdxyz = sys.argv[1].split(",")
    print("starting")
    if not len(whdxyz)==6:
        print(f"Length of parameter is {len(whdxyz)} rather than the expected 6 members.")
        return
    wdh = [float(whdxyz[f]) for f in range(0,3) ]
    xyz = [float(whdxyz[f]) for f in range(3,6) ]
    print(f"moving box to centerpoint{xyz} and setting dimensions to {wdh}")

    doc = Metashape.app.document
    
    chunk = doc.chunk
    projname = Path(doc.path).stem
    outputfolder = Path(doc.path).parent
    print(f"projectname:{projname}, outputfolder:{outputfolder}")
    _= MetashapeFileSingleton.getMetashapeDoc(projname,outputfolder,doc)
    print("Initialized singleton")
    reorienttask = MetashapeTask_ResizeBoundingBox({"input":"","output":outputfolder,"projectname":projname,"chunkname":chunk.label,"width_depth_height":wdh,"centerpoint":xyz})
    if reorienttask.setup():
        print("Executing detect markers from thresholded images")
        reorienttask.execute()
    else:
        print("Failed because reorient task setup failed.")
    reorienttask.exit()

LABEL = "Reize Region."
Metashape.app.addMenuItem(LABEL, ResizeBoundingBox )
print("To execute this script press {}".format(LABEL))