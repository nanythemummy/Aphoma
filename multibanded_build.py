import argparse
import re
import pathlib import Path
import glob
from queue import Queue
from util.Configurator import Configurator
from util.PipelineLogging import getLogger as getGlobalLogger
from util.util import * 
from tasks import BaseTask, ConversionTasks, MaskingTasks, MetashapeTasks, BlenderTasks
from util.InstrumentationStatistics import InstrumentationStatistics
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton

def sortFilesIntoBandsByName(filepath)->dict:
    multibanded_types= Configurator.getConfig().getProperty("photogrammetry","multibanded")
    getGlobalLogger(__name__).info("Loading multibanded info from config. Now sorting files.")
    files = Path(filepath).glob("*")
    chunks = {}
    for t in multibanded_types:
        if not t["name"] in chunks.keys():
            chunks[t["name"]] ={"front":
                                {"regex":re.compile(r"\S+_Front"+re.escape(t["path"])+r"[0-9]*.jpg",re.IGNORECASE),
                                  "files":[]
                                  },
                                "back":
                                {"regex":re.compile(r"\S+_Back"+re.escape(t["path"])+r"[0-9]*.jpg",re.IGNORECASE),
                                "files":[]
                                }
            }
    for file in files:
        for _, info in chunks.items():
            mf = info["front"]["regex"].match(file.name)
            mb = info["back"]["regex"].match(file.name)
            if mf:
                info["front"]["files"].append(file)
                break
            elif mb:
                info["back"]["files"].append(file)
                break
    getGlobalLogger(__name__).info("The following bands exist with the following number of pics, respectively. %s",
                                  [(a,b,len(chunks[a][b]["files"])) for a in chunks.keys() for b in chunks[a].keys() ] )
    return chunks

def executeTasklist(taskqueue:Queue):
    
    getGlobalLogger(__name__).info("Executing Tasklist.")
    succeeded = True
    while(succeeded):
        task = taskqueue.get()
        succeeded &= task.setup()
        if succeeded:
            succeeded &= task.execute()
            task.exit()
        if taskqueue.empty():
            getGlobalLogger(__name__).info("Finished the tasklist, ending.")
            break
    InstrumentationStatistics.getStatistics().logReport()
    InstrumentationStatistics.destroyStatistics()
    MetashapeFileSingleton.destroyDoc() #gets created by metashape tasks "align photos."

def setupTasksPhaseOne(chunks:dict,sourcedir,projectname,projectdir):
    tasks = Queue()
    getGlobalLogger(__name__).info("Building Tasklist.")
   
    for k,item in chunks.items():
        for fb in ["front","back"]:
            tasks.put(MetashapeTasks.MetashapeTask_AlignPhotos({"input":sourcedir,
                                                        "output":projectdir,
                                                        "maskoption":MaskingOptions.NOMASKS,
                                                        "maskpath":"masks",
                                                        "projectname":projectname,
                                                        "chunkname":f"{projectname}_{fb}{k}",
                                                        "photos":item[fb]["files"]
                                                        }))
            tasks.put(MetashapeTasks.MetashapeTask_ErrorReduction({"input":sourcedir,
                                                        "output":projectdir,
                                                        "projectname":projectname,
                                                        "chunkname":f"{projectname}_{fb}{k}"

            }))
            if k in ("ir","vis"):
                tasks.put(MetashapeTasks.MetashapeTask_DetectMarkers({"input":sourcedir,
                                                                    "output":projectdir,
                                                                    "projectname":projectname,
                                                                    "chunkname":f"{projectname}_{fb}{k}"}))
    getGlobalLogger(__name__).warning("Note that the resume flag has not been passed. This runs the steps through marker detection and stops to allow the user to place markers manually.\n Run again with the resume flag to resume.")

       
    return tasks
def setupTasksPhaseTwo(chunks:dict,sourcedir,projectname,projectdir):
    tasks = Queue()
    getGlobalLogger(__name__).info("Building Tasklist.")
   
    for k,item in chunks.items():
        for fb in ["front","back"]:
            tasks.put(MetashapeTasks.MetashapeTask_AddScales({"input":sourcedir,
                                                        "output":projectdir,
                                                        "projectname":projectname,
                                                        "chunkname":f"{projectname}_{fb}{k}"}))
            if fb=="front" and k=="vis":
                tasks.put(MetashapeTasks.MetashapeTask_ReorientSpecial({"input":sourcedir,
                                                        "output":projectdir,
                                                        "projectname":projectname,
                                                        "chunkname":f"{projectname}_{fb}{k}",
                                                        "xyplane":["target 7","target 8","target 16"],
                                                        "xaxis":("target 4","target 6")}))
    tasks.put(MetashapeTasks.MetashapeTask_AlignChunks({"input":sourcedir,
                                "output":projectdir,
                                "projectname":projectname,
                                "chunkname":f"{projectname}_frontvis",
                                "alignType":AlignmentTypes.ALIGN_BY_MARKERS}))
    for i in ["front","back"]:
        tasks.put(MetashapeTasks.MetashapeTask_BuildModel({"input":sourcedir,
                                "output":projectdir,
                                "projectname":projectname,
                                "chunkname":f"{projectname}_{i}vis"}))
        tasks.put(MetashapeTasks.MetashapeTask_BuildOrthomosaic({"input":sourcedir,
                        "output":projectdir,
                        "projectname":projectname,
                        "chunkname":f"{projectname}_{i}vis"}))
    return tasks

def build_multibanded_cmd(args):
    projdir = args.projectdir
    resume = args.resume
    sourcedir = args.sourcedir
    projectname = args.projectname
    Configurator.getConfig().setProperty("photogrammetry","palette","Multibanded")
    chunks = sortFilesIntoBandsByName(sourcedir)
    if not resume:
        tasks = setupTasksPhaseOne(chunks, sourcedir,projectname,projdir)
    else:
        tasks = setupTasksPhaseTwo(chunks, sourcedir,projectname,projdir)
    executeTasklist(tasks)
        


if __name__=="__main__":
    multibandparser = argparse.ArgumentParser()

    multibandparser.add_argument("sourcedir", help="Location of raw files")
    multibandparser.add_argument("projectdir",help="location to output files")   
    multibandparser.add_argument("projectname", help="The name of the project to build.")
    multibandparser.add_argument("-r","--resume",help="Resume the process with manually added markers.",action='store_true')
    multibandparser.set_defaults(func=build_multibanded_cmd)
    args = multibandparser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        multibandparser.print_help()
