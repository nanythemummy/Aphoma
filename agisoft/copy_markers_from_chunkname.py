from pathlib import Path
import sys
import Metashape
parentpath = Path(__file__).parent.parent.absolute()
sys.path.append(str(parentpath))
from tasks.MetashapeTasksSpecial import MetashapeTask_CopyMarkersFromChunk
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from util.Configurator import Configurator


def MarkerCopy():
    #copies markers from a designated chunk to the currently selected chunk.
    chunkname = str(sys.argv[1])
    
    doc = Metashape.app.document
    chunk = doc.chunk
    projname = Path(doc.path).stem
    outputfolder = Path(doc.path).parent
    print(f"projectname:{projname}, outputfolder:{outputfolder}")
    _= MetashapeFileSingleton.getMetashapeDoc(projname,outputfolder,doc)
    print("Initialized singleton")
    task = MetashapeTask_CopyMarkersFromChunk({"input":"","output":outputfolder,"projectname":projname,"chunkname":chunk.label,"otherchunk":chunkname})
    if task.setup():
        print("Executing copy markers")
        task.execute()
    else:
        print("Failed because reorient task setup failed.")
    task.exit()



LABEL = "MarkerCopy"
Metashape.app.addMenuItem(LABEL, MarkerCopy)
print("To execute this script press {}".format(LABEL))