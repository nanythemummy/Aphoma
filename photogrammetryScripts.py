from processing import image_processing
from transfer import transferscripts

import os.path, json, argparse
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


#These scripts  takes input and arguments from the command line and delegates them elsewhere.
#For individual transfer scripts see the transfer module, likewise, see the processing module for processing scripts.

#These classes are part of a filesystem watcher which watches for the 
#appearance of a manifest file in the desired directory, then builds a model with the pictures in the manifest.
class WatcherHandler(FileSystemEventHandler):
    @staticmethod
    def on_any_event(event):
        if event.event_type=="created" and  event.src_path.endswith("Files_to_Process.txt"):
                build_model_from_manifest(event.src_path)

        
class Watcher:
    def __init__(self,watchdir):
       self.observer = Observer()
       self.watchedDir = watchdir
    def run(self):
        handler = WatcherHandler()
        self.observer.schedule(handler,self.watchedDir,recursive=True)
        self.observer.start()
        try:
            while True:
                time.sleep(5)
        except:
            self.observer.stop()
        self.observer.join()
                
        
def watch_and_process(args):
    inputdir = args.inputdir if args.inputdir else config["watcher"]["listen_directory"]
    if not inputdir:
        print("Input Directory needed if not provided in config.json. (Check Watcher:Listen_Directory)")
        return
    assert os.path.exists(inputdir) and os.path.isdir(inputdir)
    watcher = Watcher(inputdir)
    watcher.run()

#This script contains the full automation flow and is triggered by the watche
def build_model_from_manifest(manifest):
    try:
        from photogrammetry import MetashapeTools
        filestoprocess=[]
        parentdir= os.path.abspath(os.path.join(manifest,os.pardir))
        projname = parentdir.split(os.sep)[-1] #forward slash should work since os.path functions convert windows-style paths to unix-style.
        with open(manifest,"r") as f:
            filestoprocess = f.read().split(",")
        #if the configured project directory doesn't exist, make it.
        project_base =os.path.join(config["watcher"]["project_base"])
        if not os.path.exists(project_base):
            os.mkdir(project_base)
        #setup project directories.
        project_folder = os.path.join(project_base,projname)
        tiffolder = os.path.join(project_folder,"tiff")
        outputfolder = os.path.join(project_folder,"output")
        if not os.path.exists(project_folder):
            os.mkdir(project_folder)
            os.mkdir(tiffolder)
            os.mkdir(outputfolder)
        #export Camera RAW files to Tiffs
        for f in filestoprocess:
            ext = os.path.splitext(f)[1].upper()
            if ext  ==".CR2":
                image_processing.convertCR2toTIF(f,tiffolder,config["processing"])
        MetashapeTools.build_basic_model(tiffolder,project_folder,projname)
    except ImportError as e:
        print(f"{e.msg}: You should try downloading the metashape python module from Agisoft and installing it. See Readme for more details.")
        raise e
        




    
    

def build_model(args):
    try:
        from photogrammetry import MetashapeTools
        job = args.jobname
        photoinput = args.photos
        outputdir = args.outputdirectory
        MetashapeTools.build_basic_model(photoinput,outputdir,job)
    except ImportError as e:
        print(f"{e.msg}: You should try downloading the metashape python module from Agisoft and installing it. See Readme for more details.")
        raise e

#this script is for transfering files from the ortery computer to the network drive. As a final step, it leaves a manifest of the files it copied as a 
#Comma seperated list entitled "Files_To_Process.txt." This file will be used as a signal that the sending is complete by any machine listening for changes on the folder.
def transfer_to_network_folder(args):
    """Wrapper script for running the transfer functions from the command line."""
    inputdir = args.imagedirectory
    jobname = args.jobname
    def getFileCreationTime(item):
        return os.path.getctime(item)
    fs=[os.path.join(inputdir,f) for f in os.listdir(inputdir) if f.endswith("cr2")]
    filestocopy = sorted(fs,key=getFileCreationTime)
    if args.p: #if the pics need to be pruned...
       filestocopy= transferscripts.pruneOrteryPics(filestocopy,config["ortery"])
    transferto=os.path.join(config["transfer"]["networkdrive"],jobname)
    transferscripts.transferToNetworkDirectory(transferto, filestocopy,)
    manifest  = os.path.join(transferto,"Files_to_Process.txt")
    with open(manifest,"w") as f:
        f.write(",".join(filestocopy))

def convert_raw_to_format(args):
    """wrapper script for using the RAW image conversion fucntions via the command line."""
    inputdir = args.imagedirectory
    outputdir = args.outputdirectory
    if not os.path.exists(outputdir):
        os.mkdir(outputdir)
    with os.scandir(inputdir) as it: #scans through a given directory, returning an interator.
        print(inputdir)
        for f in it:
            if os.path.isfile(f):
                if f.name.upper().endswith(".CR2"): #CANON CAMERA!
                    if args.dng:
                        image_processing.convertCR2toDNG(os.path.join(f),outputdir, config["processing"])
                    if args.tif:
                        image_processing.convertCR2toTIF(os.path.join(f),outputdir, config["processing"])

def load_config():
    """Loads the configuration values in config.json and stores them in a dictionary."""
    with open('config.json') as f:
        return json.load(f)["config"]
   

config = load_config()

parser = argparse.ArgumentParser(prog="photogrammetryScripts")
subparsers = parser.add_subparsers(help="Sub-command help")
convertprocessor = subparsers.add_parser("convert", help=" Convert a Raw file to another format ")
convertprocessor.add_argument("--dng",help="Converts to dng type", action="store_true")
convertprocessor.add_argument("--tif", help = "Convert to tif type", action="store_true")
convertprocessor.add_argument("imagedirectory", help="Directory of raw files to operate on.", type=str)
convertprocessor.add_argument("outputdirectory", help="Directory to put the output processed files.", type=str)
convertprocessor.set_defaults(func=convert_raw_to_format)

transferparser = subparsers.add_parser("transfer", help="transfers files to a network drive from the specified folder.")
transferparser.add_argument("--p", help="Prunes every Nth file from Camera X, as specified in the config.json.",action="store_true")
transferparser.add_argument("jobname", help="The name of this job. This translates into a subfolder on the network drive.")
transferparser.add_argument("imagedirectory", help="Copies images from this directory to the shared network folder as specified in config.json")
transferparser.set_defaults(func=transfer_to_network_folder)

photogrammetryparser = subparsers.add_parser("photogrammetry", help="scripts for turning photographs into 3d models")
photogrammetryparser.add_argument("jobname", help="The name of the project")
photogrammetryparser.add_argument("photos", help="Place where the photos in tiff or jpeg format are stored.")
photogrammetryparser.add_argument("outputdirectory", help="Where the intermediary files for building the model and the ultimate model will be stored.")
photogrammetryparser.set_defaults(func=build_model)

watcherprocessor = subparsers.add_parser("watch", help="Watch for incoming files in the directory configured in JSON and build a model out of them.")
watcherprocessor.add_argument("inputdir", help="Optional input directory to watch. The watcher will watch config:watcher:listen_directory by default.", default="")
watcherprocessor.set_defaults(func=watch_and_process)      

args = parser.parse_args()
if hasattr(args,"func"):
    args.func(args)
else:
    parser.print_help()

