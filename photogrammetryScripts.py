from processing import image_processing
from transfer import transferscripts
import shutil
import msvcrt
import os.path, json, argparse
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from util import util

#Global Variables
#because the callback methods are static for the watchers, we need a place to store the manifest of the files they are transfering.
MANIFEST = None
#This is the config file. I'm storing it in a global variable so I don't have to pass it or load it from disk constantly.
CONFIG = {}

#These scripts  takes input and arguments from the command line and delegates them elsewhere.
#For individual transfer scripts see the transfer module, likewise, see the processing module for processing scripts.

def process_images(args):
    """Entry point for one-off image processing via the process command. Runs lens profile corrections and color correction
    on an image and resaves it as a tif in the directory specified. 
    
    Parameters:
    args: an argument object passed by the command line that has attributes inputimage (str) and outputdir (str)
      
    """
    image_processing.process_image(args.inputimage,args.outputdir,CONFIG["processing"])

class Manifest:
    """Class that manages the manifest written to the disk by the listen and send script on the ortery computer. Adds files to an
    internal list and writes them to disk when asked."""
    def __init__(self, projectname):
        self.sentfiles = []
        self.projectname = projectname
    def addFile(self, filepath):
        """Adds a file to the manifest.
        
        Parameters:
        ---------
        filepath: the full path of the file to add.
        """
        self.sentfiles.append(filepath)
    def finalize(self, outputdir):
        """Writes the manifest to disk.
        
        Parameters:
        ----------
        outputdir: the place to write the manifest file.
        returns: the path+filename that it wrote.
        """
        outputjson = {self.projectname:self.sentfiles}
        filenametowrite = os.path.join(outputdir,f"{self.projectname}_manifest.txt")
        with open(filenametowrite,'w',encoding='utf-8') as f:
            json.dump(outputjson,f)
        return filenametowrite

def verifyManifest(manifest:dict, basedir):
    """Goes through a dictionary taken from a manifest file on disk and checks to see that all of
    the RAW files are there, all the mask files have been made, and all of the tifs have been made.
    
    Parameters"
    ---------------
    manifest: A dict containing a list of files of the format projectname:[filenames]
    basedir: the base directory to look for the rawfiles, tifs, and masks, which are in subfolders called tifs and masks.
    
    returns: succeeded, full_manifest, where succeeded is true if all the masks and tifs and raw files expected were found, and 
    manifest contains each of these files and their full paths in the format {"raw":[],"tif":[],"masks":[]}"""
    #check to see if all the masks and tifs have been made for this manifest.
    foundallfiles=True
    files = manifest[list(manifest.keys())[0]]
    fullmanifest = {"raw":[],"masks":[],"tifs":[]}
    for f in files:
        basename_with_ext = os.path.split(f)[1]
        basename = os.path.splitext(basename_with_ext)[0]
        if os.path.exists(os.path.join(basedir,basename_with_ext)):
            fullmanifest["raw"].append(os.path.join(basedir,basename_with_ext))
            tifpath = os.path.join(basedir,"tifs")
            if os.path.exists(os.path.join(tifpath,f"{basename}.tif")):
                fullmanifest["tifs"].append(os.path.join(tifpath,f"{basename}.tif"))
                maskpath = os.path.join(basedir,"masks")
                maskext=CONFIG["photogrammetry"]["mask_ext"]
                if os.path.exists(os.path.join(maskpath,f"{basename}.{maskext}")):
                    fullmanifest["masks"].append(os.path.join(maskpath,f"{basename}.{maskext}"))
                else:
                    print(f"Warning: did not find mask for {basename_with_ext} in {maskpath}")
                    foundallfiles &= False
            else:
                print(f"Warning: did not find tif for{basename_with_ext} in {tifpath}")
                foundallfiles &= False
        else:
            print(f"Warning: did not find RAW file: {basename_with_ext} in {basedir}")
            foundallfiles &= False
    return foundallfiles,fullmanifest

class WatcherSenderHandler(FileSystemEventHandler):
    """Listen in the specified directory for cr2 files. It extends Watchdog.FilesystemEventHandler"""
    @staticmethod
    def on_any_event(event):
        """Event handler for any file system event. When an event of the type file created happens, if a CR2 file is created, the files will be processed and converted to TIF
        if a manifest file is created, a model will be built based on the manifest's files.
        Parameters:
        -------------------
        event: a watchdog.event from the watchdog library.
        """
        if event.event_type=="created" and event.src_path.upper().endswith(".CR2"):
            config = CONFIG["transfer"]
            transferscripts.transferToNetworkDirectory(config["networkdrive"], [event.src_path])
            global MANIFEST
            MANIFEST.addFile(event.src_path)

class WatcherRecipientHandler(FileSystemEventHandler):
    """This is the handler class for the watcher. It handles any filesystem event that happens while the watcher is running.
    It extends Watchdog.FilesystemEventHandler."""
    @staticmethod
    def on_any_event(event):
        """Event handler for any file system event. When an event of the type file created happens, if a CR2 file is created, the files will be processed and converted to TIF
        if a manifest file is created, a model will be built based on the manifest's files.
        Parameters:
        -------------------
        event: a watchdog.event from the watchdog library.
        """
        inputdir = CONFIG["watcher"]["listen_directory"]
        if event.event_type=="modified":

            if event.src_path.upper().endswith(".CR2"):
                processedpath = os.path.join(inputdir,"tifs")
                maskpath = os.path.join(inputdir,"masks")
                tiffile=image_processing.process_image(event.src_path,processedpath,CONFIG["processing"])
                image_processing.build_masks_with_droplet(tiffile, maskpath,CONFIG["processing"])

            elif event.src_path.endswith("_manifest.txt"):
                build_model_from_manifest(event.src_path)

class Watcher:
    """These classes are part of a filesystem watcher which watches for the 
    appearance of a manifest file in the desired directory, then builds a model with the pictures
    
    Methods:
    ------------------------
    __init__(self,directory):initializes the class to watch a particular directory, configurabe in config.json.
    run(): makes a watcherHandler object and waits for it to intercept filesystem events.
    """
    def __init__(self,watchdir:str, isSender = False, projectname=""):
        self.observer = Observer()
        self.watched_dir = watchdir
        self.isSender = isSender
        self.projectname = projectname

    def run(self):
        """Manages the threads for the watcher scripts. Basically schedules threads to listen for changes to a folder on the filesystem
        and sleeps until there is either an exception or the user presses the F key. Note that this non-blocking user input check is 
        Windows Only and will have to be fixed to make this script mac/linux compatible. When the user hits the F key, if they are running
        the listen_and_send scripts, it will send a manifest of the files that were transfered."""
        if not self.isSender:
            handler = WatcherRecipientHandler()
        else:
            global MANIFEST
            MANIFEST = Manifest(self.projectname)
            handler = WatcherSenderHandler()
        self.observer.schedule(handler,self.watched_dir,recursive=True)
        self.observer.start()
        try:
            listening=True
            print("Type F to Finish.")           
            while listening :
                time.sleep(5)
                if msvcrt.kbhit():
                    if msvcrt.getch()==b'F':
                        listening=False
                        self.observer.stop()
        except Exception:
            self.observer.stop()
        self.observer.join()
        if  self.isSender and MANIFEST:
            manifestpath=MANIFEST.finalize(".")
            transferscripts.transferToNetworkDirectory(CONFIG["transfer"]["networkdrive"],[os.path.abspath(manifestpath)])

def listen_and_send(args):
    """Listens for incoming cr2 files and sends them to the network drive to be converted to tifs and then processed"

    Parameters:
    --------------------------
    args:Argument object from the command line with the following attributes: inputdir: a directory to listen on, in this case, the palce where
    pics will be created by the photography software . 
    Projectname: a projectname to be written to the manifest which will be sent when pics are finalized.
    """
    inputdir =  CONFIG["watcher"]["listen_and_send"]
    if not os.path.exists(inputdir):
        print(f"Cannot listen on a directory that does not exist: {inputdir}")
    watcher = Watcher(inputdir,isSender=True, projectname = args.projectname)

    watcher.run()
        
def watch_and_process(args):
    """function that controls the watcher script which initializes a build when pictures and a manifest are added to a specified directory.
    Parameters:
    ---------------
    args: Argument object handed from the command line which has the following attributes:
    inputdir: a directory to listen on. If this is not specified in the command line, the watcher->listen directory 
    will be used from config.json.
    """
    inputdir = args.inputdir if args.inputdir else CONFIG["watcher"]["listen_directory"]
    if not inputdir:
        print("Input Directory needed if not provided in config.json. (Check Watcher:Listen_Directory)")
        return
    watcher = Watcher(inputdir, isSender=False)
    watcher.run()

#This script contains the full automation flow and is triggered by the watcher
def build_model_from_manifest(manifestfile:str):
    """Builds a model from the files listed in a text file manifest.

    Parameters:
    -----------
    manifest: A path to a text file manifest with a comma seperated list of paths to image files.
    """
    filestoprocess=[]
    parentdir= os.path.abspath(os.path.join(manifestfile,os.pardir))
    manifest = {}
    with open(manifestfile,"r",encoding="utf-8") as f:
        manifest = json.load(f)
    projname = list(manifest.keys())[0]
    succeeded, filestoprocess = verifyManifest(manifest, parentdir)
    if succeeded:
        #if the configured project directory doesn't exist, make it.
        project_base =os.path.join(CONFIG["watcher"]["project_base"])
        if not os.path.exists(project_base):
            os.mkdir(project_base)
        #setup project directories.
        project_folder = os.path.join(project_base,projname)
        if not os.path.exists(project_folder):
            os.mkdir(project_folder)
        raw = os.path.join(project_folder,"raw")
        util.move_file_to_dest(filestoprocess["raw"],raw)
        masks = os.path.join(project_folder,CONFIG["photogrammetry"]["mask_path"])
        util.move_file_to_dest(filestoprocess["masks"],masks)
        tifs = raw = os.path.join(project_folder,"tif")
        util.move_file_to_dest(filestoprocess["tifs"],tifs)
        build_model(projname,tifs,project_folder,CONFIG,False)

        
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
        print("Converting files if needed.")                        
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
            print("Building Masks")
            maskpath = os.path.join(outputdir,config["photogrammetry"]["mask_path"])
            if not os.path.exists(maskpath):
                os.mkdir(maskpath)
                image_processing.build_masks_with_droplet(processedpath,maskpath,config["processing"])         
        print("Building Model")
        MetashapeTools.build_basic_model(processedpath,jobname,outputdir, config["photogrammetry"])
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
    nomasks = args.nomasks
    build_model(job,photoinput,outputdir,CONFIG,nomasks)
    


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
       filestocopy= transferscripts.pruneOrteryPics(filestocopy,CONFIG["ortery"])
    transferto=os.path.join(CONFIG["transfer"]["networkdrive"],jobname)
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
    input = args.inputdir
    output = args.outputdir
    image_processing.build_masks_with_droplet(input,output,CONFIG["processing"])

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
                        image_processing.convert_CR2_to_DNG(os.path.join(f),outputdir, CONFIG["processing"])
                    if args.tif:
                        image_processing.convert_CR2_to_TIF(os.path.join(f),outputdir, CONFIG["processing"])
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

CONFIG = load_config()

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

watcherparser = subparsers.add_parser("watch", help="Watch for incoming files in the directory configured in JSON and build a model out of them.")
watcherparser.add_argument("inputdir", help="Optional input directory to watch. The watcher will watch config:watcher:listen_directory by default.", default="")
watcherparser.set_defaults(func=watch_and_process)      

listensendparser = subparsers.add_parser("listenandsend", help="listen for new cr2 files in the specified subdirectory and send them to the network drive, recording them in a manifest.")
listensendparser.add_argument("inputdir", help="Optional input directory to watch. The watcher will watch config:watcher:listen_directory by default.", default="")
listensendparser.add_argument("projectname", help="Optional input directory to watch. The watcher will watch config:watcher:listen_directory by default.", default="")
listensendparser.set_defaults(func=listen_and_send)    

maskparser = subparsers.add_parser("mask", help="Build Masks for files in a folder using a photoshop droplet.")
maskparser.add_argument("inputdir", help="Photos to mask")
maskparser.add_argument("outputdir",help="location to store masks")   
maskparser.set_defaults(func=build_masks)


args = parser.parse_args()
if hasattr(args,"func"):
    args.func(args)
else:
    parser.print_help()

