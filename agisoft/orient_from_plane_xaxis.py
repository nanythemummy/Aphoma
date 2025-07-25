from pathlib import Path
import sys
import Metashape
parentpath = Path(__file__).parent.parent.absolute()
sys.path.append(str(parentpath))
from tasks import MetashapeTasks
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from util.Configurator import Configurator


def reorientOnPalette():
    print("Oh, Hai. I'm going to try to reorient this.")
    doc = Metashape.app.document
   
    chunk = doc.chunk
    projname = Path(doc.path).stem
    outputfolder = Path(doc.path).parent
    print(f"projectname:{projname}, outputfolder:{outputfolder}")
    _= MetashapeFileSingleton.getMetashapeDoc(projname,outputfolder,doc)
    print("Initialized singleton")
    Configurator.getConfig().setProperty("photogrammetry","palette","Multibanded")
    palette=Configurator.getConfig().getProperty("photogrammetry","palette")
    reorienttask = MetashapeTasks.MetashapeTask_ReorientSpecial({"input":"","output":outputfolder,"projectname":projname,"chunkname":chunk.label})
    if reorienttask.setup():
        print("Executing reorientation special")
        reorienttask.execute()
    else:
        print("Failed because reorient task setup failed.")
    reorienttask.exit()

LABEL = "Reorient on a plane specified in palettes."
Metashape.app.addMenuItem(LABEL, reorientOnPalette)
print("To execute this script press {}".format(LABEL))