from processing import image_processing
from transfer import transferscripts
import shutil
import os.path, json, argparse
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


#These scripts  takes input and arguments from the command line and delegates them elsewhere.
#For individual transfer scripts see the transfer module, likewise, see the processing module for processing scripts.

def process_images(args):
    """Entry point for one-off image processing via the process command. Runs lens profile corrections and color correction
    on an image and resaves it as a tif in the directory specified. 
    
    Parameters:
    args: an argument object passed by the command line that has attributes inputimage (str) and outputdir (str)
      
    """
    config = load_config()
    image_processing.process_image(args.inputimage,args.outputdir,config["processing"])



#T
class WatcherHandler(FileSystemEventHandler):
    """This is the handler class for the watcher. It handles any filesystem event that happens while the watcher is running.
    It extends Watchdog.FilesystemEventHandler."""
    @staticmethod
    def on_any_event(event):
        """Event handler for any file system event. When an event of the type file created happens, this will check to see if a manifest cile called "
        Files_to_process.txt was created. This file contains a list of image files that can be used to build a 3D Model.
        Parameters:
        -------------------
        event: a watchdog.event from the watchdog library.
        """
        if event.event_type=="modified" and  event.src_path.endswith("Files_to_Process.txt"):
                build_model_from_manifest(event.src_path)
class Watcher:
    """These classes are part of a filesystem watcher which watches for the 
    appearance of a manifest file in the desired directory, then builds a model with the pictures
    
    Methods:
    ------------------------
    __init__(self,directory):initializes the class to watch a particular directory, configurabe in config.json.
    run(): makes a watcherHandler object and waits for it to intercept filesystem events.
    """
    def __init__(self,watchdir:str):
        self.observer = Observer()
        self.watched_dir = watchdir
    def run(self):
        handler = WatcherHandler()
        self.observer.schedule(handler,self.watched_dir,recursive=True)
        self.observer.start()
        try:
            while True:
                time.sleep(5)
        except Exception:
            self.observer.stop()
        self.observer.join()
                
        
def watch_and_process(args):
    """function that controls the watcher script which initializes a build when pictures and a manifest are added to a specified directory.
    Parameters:
    ---------------
    args: Argument object handed from the command line which has the following attributes:
    inputdir: a directory to listen on. If this is not specified in the command line, the watcher->listen directory 
    will be used from config.json.
    """
    inputdir = args.inputdir if args.inputdir else config["watcher"]["listen_directory"]
    if not inputdir:
        print("Input Directory needed if not provided in config.json. (Check Watcher:Listen_Directory)")
        return
    assert os.path.exists(inputdir) and os.path.isdir(inputdir)
    watcher = Watcher(inputdir)
    watcher.run()

#This script contains the full automation flow and is triggered by the watcher
def build_model_from_manifest(manifest:str):
    """Builds a model from the files listed in a text file manifest.

    Parameters:
    -----------
    manifest: A path to a text file manifest with a comma seperated list of paths to image files.
    """
    config = load_config()
    filestoprocess=[]
    parentdir= os.path.abspath(os.path.join(manifest,os.pardir))
    projname = parentdir.split(os.sep)[-1] #forward slash should work since os.path functions convert windows-style paths to unix-style.
    with open(manifest,"r",encoding="utf-8") as f:
        filestoprocess = f.read().split(",")
    #if the configured project directory doesn't exist, make it.
    project_base =os.path.join(config["watcher"]["project_base"])
    if not os.path.exists(project_base):
        os.mkdir(project_base)
    #setup project directories.
    project_folder = os.path.join(project_base,projname)
    if not os.path.exists(project_folder):
        os.mkdir(project_folder)
    raw = os.path.join(project_folder,"RAW")
    if not os.path.exists(raw):
        os.mkdir(raw)
    #export Camera RAW files to Tiffs
    for f in filestoprocess:
        shutil.copyfile(f,os.path.join(raw,os.path.basename(f)))
    build_model(projname,raw,project_folder,config,False)

        
def build_model(jobname,inputdir,outputdir,config,nomasks=False):
    """Given a folder full of pictures, this function builds a 3D Model.

    Parameters:
    ------------------
    jobname: the name of the model to be built.
    inputdir: a folder full of pictures in either CR2 or TIF format.
    outputdir: The folder in which the model will be placed along with its intermediary files.
    config: the full contents of config.json.
    nomasks: boolean value determining whether to build masks or not.
    """
    try:
        from photogrammetry import MetashapeTools
        if not os.path.exists(outputdir):
            os.mkdir(outputdir)

        processedpath = inputdir
        with os.scandir(inputdir) as it:
            for f in it:
                if os.path.isfile(f):
                    if f.name.upper().endswith(".CR2"):
                        tifpath = os.path.join(outputdir,"TIFs")
                        if not os.path.exists(tifpath):
                            os.mkdir(tifpath)
                        image_processing.process_image(f.path,tifpath,config['processing'])
                        processedpath = tifpath       
        if nomasks is False:
            maskpath = os.path.join(outputdir,config["photogrammetry"]["mask_path"])
            if not os.path.exists(maskpath):
                os.mkdir(maskpath)
                image_processing.build_masks_with_droplet(processedpath,maskpath,config["processing"])         
        MetashapeTools.buildBasicModel(processedpath,jobname,outputdir, config["photogrammetry"])
    except ImportError as e:
        print(f"{e.msg}: You should try downloading the metashape python module from Agisoft and installing it. See Readme for more details.")
        raise e
    
def build_model_cmd(args):
    """The wrapper function that extracts arguments from the command line and runs the build model function with the correct params based on them.
    Parameters:
    -------------------
    args: An argument object form the command line containing the following attributes: jobname (name of the job), photos (directory with photos in it), and
    outputdir (directory in which the project will be built.)"""

    job = args.jobname
    photoinput = args.photos
    outputdir = args.outputdirectory
    config = load_config()
    nomasks = args.nomasks
    build_model(job,photoinput,outputdir,config,nomasks)
    


def transfer_to_network_folder(args):
    """This script is for transfering files from the ortery computer to the network drive. 
    
    It copies the files to the drive specified in config.json under transfer->networkdrive. 
    Then, as a final step, it leaves a manifest of the files it copied as a comma seperated list entitled "Files_To_Process.txt." 
    This file will be used as a signal that the sending is complete by any machine listening for changes on the folder.

    Parameters:
    ------------
    args: an arguments object with the following attributes: imagedirectory (a directory of images to transfer), 
    jobname (the name of the job associated with these)
    p: a flag that is true or false, which determines whether these pictures need to be pruned. The ortery takes too many pictures for 
    some views. THis makes the process take longer than needed and adds sources of error at certain angels. To fix it, we can delete a fraction
    of the pictures from each photography angle. The configuration for this is located under config.json->transfer->ortery
."""
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


def build_masks(args):
    """Wrapper script for building masks from contents of a folder using a photoshop droplet.
    Parameters:
    -----------
    args: an object containing attributes which get passed in from the command line.  These are:
    inputdir: the directory of pictures that need to be masked in TIF format.
    output: the directory where the masks need to get copied when the masking is done.
    """
    config = load_config()
    input = args.inputdir
    output = args.outputdir
    image_processing.build_masks_with_droplet(input,output,config["processing"])

def convert_raw_to_format(args):
    """wrapper script for using the RAW image conversion fucntions via the command line.
    Parameters:
    ---------
    args: an object containing atributes passed in from the command line. These are: 
    inputdir (a directory of images to convert)
    outputdir (a place to put the converted images.)
    """
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
                        image_processing.convert_CR2_to_DNG(os.path.join(f),outputdir, config["processing"])
                    if args.tif:
                        image_processing.convert_CR2_to_TIF(os.path.join(f),outputdir, config["processing"])
                    if args.jpg:
                        image_processing.convertToJPG(os.path.join(f),outputdir)
                elif f.name.upper().endswith("TIF") and args.jpg:
                    image_processing.convertToJPG(os.path.join(f),outputdir)

def load_config():
    """Loads the configuration values in config.json and stores them in a dictionary.
    returns: a dictionary containing configuration values.
    """
    with open('config.json') as f:
        return json.load(f)["config"]
   

config = load_config()

parser = argparse.ArgumentParser(prog="photogrammetryScripts")
subparsers = parser.add_subparsers(help="Sub-command help")
convertprocessor = subparsers.add_parser("convert", help=" Convert a Raw file to another format ")
convertprocessor.add_argument("--dng",help="Converts RAW to dng type", action="store_true")
convertprocessor.add_argument("--tif", help = "Convert RAW to tif type", action="store_true")
convertprocessor.add_argument("--jpg", help="Converts TIF to jpg.", action="store_true")
convertprocessor.add_argument("imagedirectory", help="Directory of raw files to operate on.", type=str)
convertprocessor.add_argument("outputdirectory", help="Directory to put the output processed files.", type=str)
convertprocessor.set_defaults(func=convert_raw_to_format)

transferparser = subparsers.add_parser("transfer", help="transfers files to a network drive from the specified folder.")
transferparser.add_argument("--p", help="Prunes every Nth file from Camera X, as specified in the config.json.",action="store_true")
transferparser.add_argument("jobname", help="The name of this job. This translates into a subfolder on the network drive.")
transferparser.add_argument("imagedirectory", help="Copies images from this directory to the shared network folder as specified in config.json")
transferparser.set_defaults(func=transfer_to_network_folder)



imageprocessing  = subparsers.add_parser("process", help="Color Processing Functions")
imageprocessing.add_argument("inputimage", help="image to process")
imageprocessing.add_argument("outputdir", help="Directory where the final processed image will be stored.")
imageprocessing.set_defaults(func=process_images)

photogrammetryparser = subparsers.add_parser("photogrammetry", help="scripts for turning photographs into 3d models")
photogrammetryparser.add_argument("jobname", help="The name of the project")
photogrammetryparser.add_argument("photos", help="Place where the photos in tiff or jpeg format are stored.")
photogrammetryparser.add_argument("outputdirectory", help="Where the intermediary files for building the model and the ultimate model will be stored.")
photogrammetryparser.add_argument("--nomasks", help = "Skip the mask generation step.", action = "store_true")
photogrammetryparser.set_defaults(func=build_model_cmd)

watcherprocessor = subparsers.add_parser("watch", help="Watch for incoming files in the directory configured in JSON and build a model out of them.")
watcherprocessor.add_argument("inputdir", help="Optional input directory to watch. The watcher will watch config:watcher:listen_directory by default.", default="")
watcherprocessor.set_defaults(func=watch_and_process)      

maskprocessor = subparsers.add_parser("mask", help="Build Masks for files in a folder using a photoshop droplet.")
maskprocessor.add_argument("inputdir", help="Photos to mask")
maskprocessor.add_argument("outputdir",help="location to store masks")   
maskprocessor.set_defaults(func=build_masks)


args = parser.parse_args()
if hasattr(args,"func"):
    args.func(args)
else:
    parser.print_help()

