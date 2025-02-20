from pathlib import Path
import argparse
from tasks.ConversionTasks import ConvertToJPG
from tasks.MaskingTasks import MaskAI,MaskDroplet
from processing import image_processing

from util.InstrumentationStatistics import InstrumentationStatistics, Statistic_Event_Types
from util.PipelineLogging import getLogger as getGlobalLogger
from util.Configurator import Configurator
from util.util import MaskingOptions
from queue import Queue
HALT = False
def buildEventQueue(states:list)->Queue:
    """given a list full of tasks and their parameters,
      this will construct a queue of events to execute to accomplish the tasks. The list should be in the format:
       [{"name":"taskname","kwargs":{dictionary of arguments the task expects}}]

    Parameters:
    -----------
    args: taskqueue -- a queue full of objects that should be subclassed off of tasks::basetask.
    """
    taskqueue = Queue()
    for state in states:
        tempstate = None
        sname = state["name"]
        sargs = state["kwargs"]
        if sname == "Masking":
            if sargs["maskoption"]== MaskingOptions.MASK_AI.value:
                tempstate = MaskAI(sargs)
            elif sargs["maskoption"]==MaskingOptions.MASK_CONTEXT_AWARE_DROPLET.value:
                tempstate = MaskDroplet(sargs)
        elif sname =="ConvertJPG":
            tempstate = ConvertToJPG(sargs)
        if tempstate:
            taskqueue.put(tempstate)
    return taskqueue

def executeTaskQueue(taskqueue:Queue):
    """Executes a series of tasks in a task queue.It checks to see if the setup phase of each task passes,'
        runs the execute phase, and then runs the cleanup code in exit.

    Parameters:
    -----------
    args: taskqueue -- a queue full of objects that should be subclassed off of tasks::basetask.
    """
    while not taskqueue.empty() and not HALT:
        state = taskqueue.get()
        if state.setup():
            state.execute()
            state.exit()
    InstrumentationStatistics.getStatistics().logReport()
    InstrumentationStatistics.destroyStatistics()

def build_masks_cmd(args):
    """Wrapper script for building masks from contents of a folder using a photoshop droplet.
    Parameters:
    -----------
    args: an object containing attributes which get passed in from the command line.  These are:
    inputdir: the directory of pictures that need to be masked in TIF format.
    output: the directory where the masks need to get copied when the masking is done.
    """
    inputdir = args.rawdir
    output = args.outputdir
    maskoption = args.maskoption
    intermediary = args.sourcedir

    tasks = [
        {"name":"ConvertJPG","kwargs":{"input":inputdir,"output":intermediary}},
        {"name":"Masking","kwargs":{"input":intermediary,"output":output,"maskoption":int(maskoption)}}
        ]
    sm= buildEventQueue(tasks)
    executeTaskQueue(sm)
    #image_processing.build_masks(input,output,int(args.maskoption))

if __name__=="__main__":
    _LOGGER = getGlobalLogger(__name__)
    _CONFIG = Configurator.getConfig()
    parser = argparse.ArgumentParser(prog="photogrammetryScripts")
    subparsers = parser.add_subparsers(help="Sub-command help")
    maskparser = subparsers.add_parser("mask", help="Build Masks for files in a folder using various methods.")
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

    maskparser.set_defaults(func=build_masks_cmd)
    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()