from pathlib import Path
from os import mkdir
from util.PipelineLogging import getLogger
import Metashape
#provides a singleton wrapper around a metashape document so that multiple tasks can access it.
class MetashapeFileSingleton():
    _METASHAPE_FILE = None
    def __init__(self,projectdir:Path ,projectname:Path,doc=None):

        self._projdir = projectdir
        self._projname = projectname
        if doc is None:
            if not self._projdir.exists():
                mkdir(self._projdir)
            self._metashapedoc = Metashape.Document()
            psxfile = Path(self._projdir,f"{self._projname}.psx")

            if psxfile.exists():
                self._metashapedoc.open(str(psxfile))
                getLogger(__name__).info("Opening existing psx file %s",psxfile)
            else:
                self._metashapedoc.save(str(psxfile))
                getLogger(__name__).info("Creating psx file %s",psxfile)
        else:
            self._metashapedoc = doc

    def getProjectPath(self):
        return Path(self._metashapedoc.path)
    def getDoc(self):
        return self._metashapedoc


    def closeProject(self):
        #do whatever needs to be done here.
        getLogger(__name__).info("Gently suggesting that the doc file %s be garbage collected",self._metashapedoc.path)
        self._metashapedoc = None
        
               

    @staticmethod 
    def getMetashapeDoc(projectname, outputdir,doc=None,):

        if MetashapeFileSingleton._METASHAPE_FILE  is not None:
            required_directory = Path(outputdir,f"{projectname}.psx")
            if MetashapeFileSingleton._METASHAPE_FILE.getProjectPath() != required_directory:
                MetashapeFileSingleton._METASHAPE_FILE.closeProject()
                MetashapeFileSingleton._METASHAPE_FILE = MetashapeFileSingleton(outputdir,projectname)
        elif doc is not None:
            MetashapeFileSingleton._METASHAPE_FILE = MetashapeFileSingleton(outputdir,projectname,doc)
        else:
            MetashapeFileSingleton._METASHAPE_FILE=MetashapeFileSingleton(outputdir,projectname)
        return MetashapeFileSingleton._METASHAPE_FILE.getDoc()

    @staticmethod
    def destroyDoc():
        if MetashapeFileSingleton._METASHAPE_FILE  is not None:
            MetashapeFileSingleton._METASHAPE_FILE.closeProject()



