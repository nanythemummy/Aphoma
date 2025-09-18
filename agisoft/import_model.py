from pathlib import Path
import sys
import Metashape
parentpath = Path(__file__).parent.parent.absolute()
sys.path.append(str(parentpath))
from tasks.MetashapeTasksSpecial import MetashapeTask_ImportModel
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from util.Configurator import Configurator


def loadModel():
    modelpath = Path(sys.argv[1])

    doc = Metashape.app.document
    
    chunk = doc.chunk
    projname = Path(doc.path).stem
    outputfolder = Path(doc.path).parent
    print(f"projectname:{projname}, outputfolder:{outputfolder}")
    _= MetashapeFileSingleton.getMetashapeDoc(projname,outputfolder,doc)
    print("Initialized singleton")
    importmodeltask = MetashapeTask_ImportModel({"input":"","output":outputfolder,"projectname":projname,"chunkname":chunk.label,"modelfilename":modelpath})
    if importmodeltask.setup():
        importmodeltask.execute()

    importmodeltask.exit()

LABEL = "ImportModel"
Metashape.app.addMenuItem(LABEL, loadModel )
print("To execute this script press {}".format(LABEL))