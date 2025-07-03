import argparse
import re
import pathlib
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
    succeeded = True
    while(succeeded):
        task = taskqueue.get()
        succeeded &= task.setup()
        if succeeded:
            succeeded &= task.execute()
            task.exit()
        if taskqueue.empty():
            break
    InstrumentationStatistics.getStatistics().logReport()
    InstrumentationStatistics.destroyStatistics()
    MetashapeFileSingleton.destroyDoc() #gets created by metashape tasks "align photos."

def setupTasks(chunks:dict,sourcedir,projectname,projectdir):
    tasks = Queue()
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
    return tasks

def build_multibanded_cmd(args):
    projdir = args.projectdir
    sourcedir = args.sourcedir
    projectname = args.projectname
    getGlobalLogger(__name__).info("Loading multibanded info from config.")
    chunks = sortFilesIntoBandsByName(sourcedir)
    tasks = setupTasks(chunks, sourcedir,projectname,projdir)
    executeTasklist(tasks)
        


if __name__=="__main__":
    multibandparser = argparse.ArgumentParser()

    multibandparser.add_argument("sourcedir", help="Location of raw files")
    multibandparser.add_argument("projectdir",help="location to output files")   
    multibandparser.add_argument("projectname", help="The name of the project to build.")
    multibandparser.set_defaults(func=build_multibanded_cmd)
    args = multibandparser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        multibandparser.print_help()
