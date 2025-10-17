from pathlib import Path
import sys
import Metashape
parentpath = Path(__file__).parent.parent.absolute()
sys.path.append(str(parentpath))
from tasks.MetashapeTasksSpecial import MetashapeTask_CopyBoundingBoxToChunks
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
#this is cribbed from wiki.agisoft.com/s Copy Bounding Box script


def CopyBB():

    doc = Metashape.app.document
    
    chunk = doc.chunk
    projname = Path(doc.path).stem
    outputfolder = Path(doc.path).parent
    print(f"projectname:{projname}, outputfolder:{outputfolder}")
    _= MetashapeFileSingleton.getMetashapeDoc(projname,outputfolder,doc)
    print("Initialized singleton")
    chunks = [c for c in doc.chunks if c.label !=chunk.label]
    print(chunks)
    tasklist = []
    tasklist.append(MetashapeTask_CopyBoundingBoxToChunks({"input":"","output":outputfolder,"projectname":projname,"chunkname":chunk.label,"chunklist":chunks}))
    for task in tasklist:
        if task.setup():
            print(f"Executing {task}")
            task.execute()
        else:
            print("Failed because reorient task setup failed.")
        task.exit()




LABEL = "CopyBB"
Metashape.app.addMenuItem(LABEL, CopyBB)
print("To execute this script press {}".format(LABEL))