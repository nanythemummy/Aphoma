from PIL import Image
from pathlib import Path
from queue import Queue
import sys
parentpath = Path(__file__).parent.parent.absolute()
sys.path.append(str(parentpath))
from tasks.ConversionTasks import ConvertToJPG,ConvertToTIF
from util.InstrumentationStatistics import InstrumentationStatistics
from util.PipelineLogging import getLogger as getGlobalLogger
from util.ErrorCodeConsts import ErrorCodes
import argparse

def buildQueue(input, output, type):
    q = Queue()
    if Path(input).exists() and Path(output).exists:
        paths = Path(input).glob("*.CR2")
        for path in paths:
            if int(type) == 0:
                q.put(ConvertToTIF({"input":path,"output":output}))
            else:
                q.put(ConvertToJPG({"input":path,"output":output}))
    return q

def execute_tasks(task_queue:Queue):
    getGlobalLogger(__name__).info("Executing Tasklist.")
    succeeded = True
    global FINISHED
    FINISHED = False
    phase = "setup"
    while(not FINISHED):
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
        if task_queue.empty():
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
    execute_tasks(tasks)
