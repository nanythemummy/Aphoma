import argparse
import sys
from pathlib import Path
from queue import Queue

parentpath = Path(__file__).parent.parent.absolute()
sys.path.append(str(parentpath))
from tasks.ConversionTasks import ConvertToJPG,ConvertToTIF
from util.InstrumentationStatistics import InstrumentationStatistics
from util.PipelineLogging import getLogger as getGlobalLogger
from util.ErrorCodeConsts import ErrorCodes


def buildQueue(inputdir:str, outputdir:str, tp:int)->Queue:
    """Function buildQueue
    Parameters: inputdir: a string with the full path of the directory containing CR2 files
    outputdir: a string with the fullpath of a directory to put the results
    tp: a numerical option corresponding to the desired destination format. 0=TIF, 1=JPG
    Builds and returns queue with tasks to convert each picture based on the desired destination format and input.
    """
    q = Queue()
    if Path(inputdir).exists() and Path(outputdir).exists:
        paths = Path(inputdir).glob("*.NEF")
        for path in paths:
            if int(tp) == 0:
                q.put(ConvertToTIF({"input":path,"output":outputdir,"profile_correction":True}))
            else:
                q.put(ConvertToJPG({"input":path,"output":outputdir,"profile_correction":False}))
    return q

def executeTasks(task_queue:Queue):
    """Function execute_tasks
    Parameters: task_queue: Tales a Queue object filled with subclasses of BaseTask.
    executes the setup, execute and exit functions on the task for each task in the queue. Returns nothing.
    """
    getGlobalLogger(__name__).info("Executing Tasklist.")
    succeeded = True
    global FINISHED
    FINISHED = False
    phase = "setup"
    while(not FINISHED):
        if not task_queue.empty():
            task = task_queue.get()
            succeeded,code = task.setup()
            if succeeded:
                phase = "execute"
                succeeded, code =task.execute()
                if succeeded:
                    phase = "exit"
                    succeeded,code = task.exit()
            if not succeeded:
                getGlobalLogger(__name__).error("Phase %s for Task %s failed with error %s",phase, str(task),ErrorCodes.numToFriendlyString(code))
                FINISHED=True
                break
        else:
            FINISHED = True
            getGlobalLogger(__name__).info("Finished the tasklist, ending.")


if "__main__" == __name__:
    parser = argparse.ArgumentParser(description="Convert RAW Files to TIF or JPG.")
    parser.add_argument('input_folder', help='Path to the input folder containing JPG images')
    parser.add_argument('output_folder', help='Directory to save the output masks')
    parser.add_argument("--convert", type = str, choices=["0","1"], 
                            help = "What do you want to convert to?\
                             0 = TIF\
                             1 =JPG",
                            default=1)
    args = parser.parse_args()
    tasks = buildQueue(args.input_folder, args.output_folder, int(args.convert))
    executeTasks(tasks)
