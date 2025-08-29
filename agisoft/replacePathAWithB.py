from pathlib import Path,PurePosixPath
import sys
import Metashape
parentpath = Path(__file__).parent.parent.absolute()
sys.path.append(str(parentpath))
from tasks.MetashapeTasks import MetashapeTask_Reorient
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from util.Configurator import Configurator


def ReplaceAB():
    #copies markers from a designated chunk to the currently selected chunk.
    paths = str(sys.argv[1])
    a,b = paths.split(",")
    doc = Metashape.app.document
    chunk = doc.chunk
    projname = Path(doc.path).stem
    for c in chunk.cameras:
        if c.type == Metashape.Camera.Type.Regular:
            temp = str(PurePosixPath(a))
            metashapepath = str(c.photo.path)
           # print(f"comparing {metashapepath} to {temp}")
            if str(temp)==metashapepath:
                print(f"replacing {metashapepath} with {str(PurePosixPath(b))}")
                c.photo.path =str(PurePosixPath(b))
                marker = chunk.addMarker()
                doc.save()
                chunk.remove(marker)
                doc.save()

def CopyAB():
    paths = str(sys.argv[1])
    a,b = paths.split(",")
    doc = Metashape.app.document
    chunk = doc.chunk
    projname = Path(doc.path).stem
    for c in chunk.cameras:
        if c.type == Metashape.Camera.Type.Regular:
            temp = str(PurePosixPath(a))
            metashapepath = str(c.photo.path)
           # print(f"comparing {metashapepath} to {temp}")
            if str(temp)==metashapepath:
                print(f"replacing {metashapepath} with {str(PurePosixPath(b))}")
                photocopy = c.photo.copy()
                photocopy.path  = str(PurePosixPath(b))
                c.photo = photocopy
                marker = chunk.addMarker()
                doc.save()
                chunk.remove(marker)
                doc.save()


LABEL = "Replace Path A With B"
Metashape.app.addMenuItem(LABEL, CopyAB)
print("To execute this script press {}".format(LABEL))