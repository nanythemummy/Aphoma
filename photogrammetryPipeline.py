from pathlib import Path
from os import listdir
import argparse
from tasks.ConversionTasks import ConvertToJPG
from tasks.MaskingTasks import MaskAI,MaskDroplet,MaskThreshold
from tasks.MetashapeTasks import *
from tasks.BlenderTasks import BlenderSnapshotTask
from processing import image_processing

from util.InstrumentationStatistics import InstrumentationStatistics, Statistic_Event_Types
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from util.PipelineLogging import getLogger as getGlobalLogger
from util.Configurator import Configurator
from util.util import MaskingOptions
from queue import Queue

_HALT = False
_STOP_ON_COMPLETED = True

def buildMetashapeTasks()->Queue:
    metashapetasks = Queue()

def buildTaskQueue(tasklist:list)->Queue:
    """given a list full of tasks and their parameters,
      this will construct a queue of events to execute to accomplish the tasks. The list should be in the format:
       [{"name":"taskname","kwargs":{dictionary of arguments the task expects}}]

    Parameters:
    -----------
    args: tasks.
    """
    taskqueue = Queue()
    for task in tasklist:
        temptask = None
        sname = task["name"]
        sargs = task["kwargs"]
        if sname == "Masking":
            if sargs["maskoption"]== MaskingOptions.MASK_AI.value:
                temptask = MaskAI(sargs)
            elif sargs["maskoption"]==MaskingOptions.MASK_THRESHOLDING.value:
                temptask =  MaskThreshold(sargs)
            elif sargs["maskoption"]==MaskingOptions.MASK_CONTEXT_AWARE_DROPLET.value:
                temptask = MaskDroplet(sargs)
        elif sname =="ConvertJPG":
            temptask = ConvertToJPG(sargs)
        elif sname =="Metashape_DetectMarkers":
            temptask = MetashapeTask_DetectMarkers(sargs)
        elif sname=="Metashape_Align":
            temptask = MetashapeTask_AlignPhotos(sargs)
        elif sname == "Metashape_ErrorReduction":
            temptask = MetashapeTask_ErrorReduction(sargs)
        elif sname == "Metashape_BuildModel":
            temptask = MetashapeTask_BuildModel(sargs)
        elif sname=="Metashape_FindScales":
            temptask = MetashapeTask_AddScales(sargs)
        elif sname=="Metashape_AlignChunks":
            temptask = MetashapeTask_AlignChunks(sargs)
        elif sname == "Metashape_BuildTextures":
            temptask = MetashapeTask_BuildTextures(sargs)
        elif sname == "Metashape_Reorient":
            temptask = MetashapeTask_Reorient(sargs)
        elif sname == "Metashape_ExportModel":
            temptask = MetashapeTask_ExportModel(sargs)
        elif sname == "Blender_Snapshot":
            temptask = BlenderSnapshotTask(sargs)
        if temptask:
            taskqueue.put(temptask)
    return taskqueue

def executeTaskQueue(taskqueue:Queue):
    """Executes a series of tasks in a task queue.It checks to see if the setup phase of each task passes,'
        runs the execute phase, and then runs the cleanup code in exit.

    Parameters:
    -----------
    args: taskqueue -- a queue full of objects that should be subclassed off of tasks::basetask.
    """
    global _STOP_ON_COMPLETED
    succeeded = True
    while succeeded and not _HALT:
        task = taskqueue.get()
        succeeded &= task.setup()
        if succeeded:
            succeeded &= task.execute()
            succeeded &= task.exit()
        if taskqueue.empty() and _STOP_ON_COMPLETED:
            break
    InstrumentationStatistics.getStatistics().logReport()
    InstrumentationStatistics.destroyStatistics()
    MetashapeFileSingleton.destroyDoc()
    _STOP_ON_COMPLETED = True
def build_conversion_masking_taskqueue(inputdir:Path, maskoption, maskpath):
    conversions=[]
    futurejpgs=[]
    extns = [".NEF",".TIF",".JPG",".CR2"]
    for fn in [Path(f) for f in listdir(inputdir)]:
        sfx = fn.suffix.upper()
        if sfx in extns: 
            conversions.append({"name":"ConvertJPG","kwargs":{"input":Path(inputdir,fn),"output":inputdir}})
            futurejpg = Path(inputdir,f"{fn.stem}.jpg")
            if not int(maskoption)==0:
                futurejpgs.append({"name":"Masking","kwargs":{"input":futurejpg,
                                        "output":maskpath,
                                        "maskoption":int(maskoption)}},)
    return conversions+futurejpgs
def build_model_cmd(args):
    """Wrapper script for building masks from contents of a folder using a photoshop droplet.
    Parameters:
    -----------
    args: an object containing attributes which get passed in from the command line.  These are:
    sourcedir: the directory of pictures that need to be masked in TIF format.
    outputdir: the directory where the masks need to get copied when the masking is done.
    maskoption: the integer method to use for building masks. (see command line help.)
    Note: intermediary files  such as jpgs made from the RAW or tif files will be placed in the same directory as those tif files /
    all models will be built from JPGs saed at 95/100 quality.
    """ 
    inputdir = args.sourcedir
    projectdir = args.projectdir
    projectname = args.projectname
    possiblepalettes = ["none","small_axes_palette","large_axes_palette","protractor","protractor2","CHI"]
    exporttype = Configurator.getConfig().getProperty("photogrammetry","export_as")
    Configurator.getConfig().setProperty("photogrammetry","palette", possiblepalettes[int(args.palette)])
    maskoption = args.maskoption
    outputfolder = Configurator.getConfig().getProperty("photogrammetry","output_path")
    tasks = []
    projects = [{"name":"main",
                 "desc":"visible light",
                 "path":inputdir}]
    tasks+= build_conversion_masking_taskqueue(inputdir,maskoption,Path(projectdir,Configurator.getConfig().getProperty('photogrammetry','mask_path')))
    for band in Configurator.getConfig().getProperty("photogrammetry","multibanded"):
        print(band)
        if Path(projectdir,band["path"]).is_dir():
            projects.append(band)
            tasks+= build_conversion_masking_taskqueue(Path(projectdir,band["path"]),
                                                       maskoption,Path(projectdir,f"{band['name']}_{Configurator.getConfig().getProperty('photogrammetry','mask_path')}"))
    
    for project in projects:
        
        outputfilename =  Path(projectdir,outputfolder,f"{util.get_export_filename(f"{projectname}_{project['name']}".replace(" ",""),exporttype)}{exporttype}")
        maskpath =Path(projectdir,Configurator.getConfig().getProperty('photogrammetry','mask_path'))
        projectinput = inputdir
        if project['name'] != "main":
            maskpath = Path(projectdir,f"{project['name']}_{Configurator.getConfig().getProperty('photogrammetry','mask_path')}")
            projectinput = Path(projectdir,project["path"])

        metashapetasks=[
            {"name":"Metashape_Align","kwargs":{"input":projectinput,
                                                "output":projectdir,
                                                "maskoption":int(maskoption),
                                                "maskpath":maskpath,
                                                "projectname":projectname,
                                                "chunkname":f"{projectname}_{project['name']}"}},
            {"name": "Metashape_DetectMarkers","kwargs":{"input":projectinput,
                                                "output":projectdir,
                                                "projectname":projectname,
                                                 "chunkname":f"{projectname}_{project['name']}"}},
            {"name": "Metashape_ErrorReduction","kwargs":{"input":projectinput,
                                                "output":projectdir,
                                                "projectname":projectname,
                                                 "chunkname":f"{projectname}_{project['name']}"}},
            {"name": "Metashape_BuildModel","kwargs":{"input":projectinput,
                                                "output":projectdir,
                                                "projectname":projectname,
                                                 "chunkname":f"{projectname}_{project['name']}"}},
            {"name": "Metashape_FindScales","kwargs":{"input":projectinput,
                                                "output":projectdir,
                                                "projectname":projectname,
                                                 "chunkname":f"{projectname}_{project['name']}"}},
            {"name": "Metashape_BuildTextures","kwargs":{"input":projectinput,
                                                "output":projectdir,
                                                "projectname":projectname,
                                                 "chunkname":f"{projectname}_{project['name']}"}},
           
        ]
        tasks+=metashapetasks
    if len(projects)>0:
        tasks.append({"name": "Metashape_AlignChunks","kwargs":{"input":inputdir,
                            "output":projectdir,
                            "projectname":projectname,
                            "chunkname":f"{projectname}_main",
                            "alignType":AlignmentTypes.ALIGN_BY_MARKERS}})
    tasks+=[{"name": "Metashape_Reorient","kwargs":{"input":projectinput,
                                                "output":projectdir,
                                                "projectname":projectname,
                                                 "chunkname":f"{projectname}_{project['name']}"}},
            {"name": "Metashape_ExportModel","kwargs":{"input":projectinput,
                                                "output":projectdir,
                                                "projectname":projectname,
                                                "chunkname":f"{projectname}_{project['name']}",
                                                "extension":exporttype,
                                                "conform_to_shape":False}},
            {"name": "Blender_Snapshot","kwargs":{"inputobj":outputfilename,
                                                "output":projectdir,
                                                "scale":True,
                                                }}]
    sm = buildTaskQueue(tasks)
    executeTaskQueue(sm)
def build_masks_cmd(args):
    """Wrapper script for building masks from contents of a folder.
    Parameters:
    -----------
    args: an object containing attributes which get passed in from the command line.  These are:
    inputdir: the directory of pictures that need to be masked in TIF format.
    output: the directory where the masks need to get copied when the masking is done.
    maskoption: the integer method to use for building masks. (see command line help.)
    sourcedir: a temporary directory for storing jpgs that get built from TIFs or RAW. These are used to build the masks.
    """
    inputdir = args.rawdir
    output = args.outputdir
    maskoption = args.maskoption
    intermediary = args.sourcedir

    tasks = [
        {"name":"ConvertJPG","kwargs":{"input":inputdir,"output":intermediary}},
        {"name":"Masking","kwargs":{"input":intermediary,"output":output,"maskoption":int(maskoption)}}
        ]
    sm= buildTaskQueue(tasks)
    executeTaskQueue(sm)
    #image_processing.build_masks(input,output,int(args.maskoption))

if __name__=="__main__":
    _LOGGER = getGlobalLogger(__name__)
    _CONFIG = Configurator.getConfig()
    parser = argparse.ArgumentParser(prog="photogrammetryScripts")
    
    subparsers = parser.add_subparsers(help="Sub-command help")
    maskparser = subparsers.add_parser("mask", help="Build Masks for files in a folder using various methods.")
    buildparser = subparsers.add_parser("build", help="Build a model using the RAW, TIF, or JPG files in a given directory.")
    maskparser.add_argument("rawdir", help="Location of raw files")
    maskparser.add_argument("outputdir",help="location to store masks")   
    maskparser.add_argument("sourcedir",help="Location of files to build model from")   
    maskparser.add_argument("--maskoption", type = str, choices=["0","1","2","3","4","5"], 
                            help = "How do you want to build masks: \
                                    0 = no masks,\
                                    1 = Photoshop droplet(context aware select), \
                                    2 = Photoshop droplet (magic wand), \
                                    3 = Canny Edge detection algorithm, \
                                    4 = Grayscale Thresholding, \
                                    5 = AI",
                            default=0)
    buildparser.add_argument("sourcedir", help="Location of raw files")
    buildparser.add_argument("projectdir",help="location to store masks")   
    buildparser.add_argument("projectname", help="The name of the project to build.")
    buildparser.add_argument("--maskoption", type = str, choices=["0","1","2","3","4","5"], 
                            help = "How do you want to build masks: \
                                    0 = no masks, \n\
                                    1 = Photoshop droplet(context aware select), \n \
                                    2 = Photoshop droplet (magic wand), \n \
                                    3 = Canny Edge detection algorithm, \n\
                                    4 = Grayscale Thresholding, \n \
                                    5 = AI \n",
                            default=0)
    buildparser.add_argument("--palette", type=str, choices=["0","1","2","3","4","5"],
                             help = "What kind of palette are you using for measurement and orientation? \
                             0= No Palette \n \
                             1= Small Axes Palette \n \
                             2= Large Axes Palette \n \
                             3= Labelled Protractor \n \
                            4= Acute Protractor \n \
                            5=CHI Markers",
                            
                             default=0)

    buildparser.set_defaults(func = build_model_cmd)
    maskparser.set_defaults(func=build_masks_cmd)
    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()