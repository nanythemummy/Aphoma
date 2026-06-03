import argparse
import shutil
from os import mkdir
from pathlib import Path
import sched, time
from util.InstrumentationStatistics import InstrumentationStatistics, Statistic_Event_Types, timed
from util.PipelineLogging import getLogger as getGlobalLogger
from util.buildManifest import Manifest

MANIFEST = None
def CopyFiles(inputdir:Path, outputdir:Path, f:Path):
    """ CopyFiles
    This function copies files from inputdir to outputdir 
    Parameters:
    ------------------
    f: the file to copy.
    inputdir: the directory from which to copy files.
    outputdir: the directory to copy files to.
    """  
    if not Path(outputdir,f).exists():
        i = str(Path(inputdir,f))
        o = str(Path(outputdir,f))
        getGlobalLogger(__name__).info("Time: %s Copying %s to %s",time.time(),i,o)
        shutil.copyfile(i,o)
        MANIFEST.addFile(i)

@timed(Statistic_Event_Types.EVENT_TAKE_PHOTO)
def RunSimulation(inputdir:Path,outputdir:Path,rate:int):
    """ RunSimulation
    This function copies files from inputdir to outputdir at a rate of x files per minute.
    Parameters:
    ------------------
    inputdir: the directory from which to copy files.
    outputdir: the directory to copy files to.
    rate: the number of pics per mintue to copy as an int.
    """  
    global MANIFEST
    MANIFEST = Manifest("OrterySim")
    allowedsuffixes = [".JPG",".TIF",".NEF",".CR2"]
    interval = 60.0/float(rate) 
    curinterval = 0.0
    s = sched.scheduler(time.time,time.sleep)
    for f in inputdir.iterdir():
        if f.is_file() and f.suffix.upper() in allowedsuffixes:
            if Path(outputdir,f.name).is_file():
                getGlobalLogger(__name__).info("File %s already exists in %s. Skipping",f.name,outputdir)
                MANIFEST.addFile(str(Path(outputdir,f.name)))
            else:
                s.enter(curinterval,1, CopyFiles,(inputdir,outputdir,f.name))
                curinterval +=interval
    s.enter(curinterval,1,MANIFEST.finalize,(outputdir,))
    s.run()

def RunSimulation_cmd(args):
    """ RunSimulation_cmd
    This is a wrapper for the RunSimulation fucntion that basically unpacks arguments and does some basic prep work before running the runsim
    command.
    Parameters:
    ------------------
    args: an object with attributes: imagedirectory (the directory of images to copy at a set rate)
        outputdir: the directory to put them in.
        rate: the rate at which the files should be copied over in x files per minute.
    """
    inputdir = Path(args.imagedirectory)
    outputdir = Path(args.outputdirectory)
    rate = int(args.rate)
    if inputdir.is_dir():
        if not outputdir.is_dir():
            mkdir(outputdir)
        RunSimulation(inputdir,outputdir,rate)
    InstrumentationStatistics.getStatistics().logReport()
    
if __name__=="__main__":
    parser = argparse.ArgumentParser(prog="OrterySimulator")
    parser.add_argument("imagedirectory", help="Directory of raw files to operate on.", type=str)
    parser.add_argument("outputdirectory", help="Directory to put the output processed files.", type=str)
    
    parser.add_argument("rate", help="Pics Per Minute", type=int)

    parser.set_defaults(func=RunSimulation_cmd)   
    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()