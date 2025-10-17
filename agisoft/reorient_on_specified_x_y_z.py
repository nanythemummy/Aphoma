from pathlib import Path
import sys
import Metashape
parentpath = Path(__file__).parent.parent.absolute()
sys.path.append(str(parentpath))
from tasks.MetashapeTasks import MetashapeTask_Reorient
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from util.Configurator import Configurator


def ReorientXYZ():
    #copies markers from a designated chunk to the currently selected chunk.
    palettename = str(sys.argv[1])
    
    doc = Metashape.app.document
    chunk = doc.chunk
    projname = Path(doc.path).stem
    outputfolder = Path(doc.path).parent
    print(f"projectname:{projname}, outputfolder:{outputfolder}")
    _= MetashapeFileSingleton.getMetashapeDoc(projname,outputfolder,doc)
    print("Initialized singleton")
    task = MetashapeTask_Reorient({"palettename":palettename,"input":"","output":outputfolder,"projectname":projname,"chunkname":chunk.label})
    if task.setup():
        print("Executing Reorient")
        task.execute()
    else:
        print("Failed because reorient task setup failed.")
    task.exit()



LABEL = "Reorient on Palette"
Metashape.app.addMenuItem(LABEL, ReorientXYZ)
print("To execute this script press {}".format(LABEL))