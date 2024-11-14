

import msvcrt
import os.path, json, argparse
from datetime import datetime
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from util.util import MaskingOptions, copy_file_to_dest, should_prune, get_export_filename
from util.PipelineLogging import getLogger as getGlobalLogger
from util.Configurator import Configurator
from util.InstrumentationStatistics import InstrumentationStatistics as statistics
from util.InstrumentationStatistics import Statistic_Event_Types
from processing import image_processing
from transfer import transferscripts

from postprocessing import MeshlabHelpers
from util.buildManifest import Manifest

def get_logger():
    return getGlobalLogger(__name__)
#Global Variables
#because the callback methods are static for the watchers, we need a place to store the manifest of the files they are transfering.
MANIFEST = None
#This is the config file. I'm storing it in a global variable so I don't have to pass it or load it from disk constantly.
_CONFIG = {}
#prune is a boolean on whether the listener should prune pictures from the ortery or not. Probably ought to come up with
# a non global var way of doing this.
PRUNE = False
#logger is a logger. all methods to go to the console in the ui should use this so that we can filter the normal metashape and debugging messages from things like 
#instrumentation.

#These scripts  takes input and arguments from the command line and delegates them elsewhere.
#For individual transfer scripts see the transfer module, likewise, see the processing module for processing scripts.

def process_images(args):
    """Entry point for one-off image processing via the process command. Runs lens profile corrections and color correction
    on an image and resaves it as a tif in the directory specified. 
    
    Parameters:
    args: an argument object passed by the command line that has attributes inputimage (str) and outputdir (str)
      
    """
    image_processing.process_image(args.inputimage,args.outputdir,_CONFIG["processing"])


def verifyManifest( manifest:dict, basedir):
    """Goes through a dictionary taken from a manifest file on disk and checks to see that all of
    the RAW files are there, all the mask files have been made, and all of the tifs have been made.
    
    Parameters"
    ---------------
    manifest: A dict containing a list of files of the format projectname:[filenames]
    basedir: the base directory to look for the rawfiles, tifs, and masks, which are in subfolders called tifs and masks.
    
    returns: succeeded, full_manifest, where succeeded is true if all the masks and tifs and raw files expected were found, and 
    manifest contains each of these files and their full paths in the format {"raw":[],"tif":[],"masks":[]}"""
    #check to see if all the masks and tifs have been made for this manifest.
    config = Configurator.getConfig()
    scratchdir = config.getProperty("watcher","temp_scratch")
    foundallfiles=True
    project = next(iter(manifest))
    files = manifest[project]["files"]
    destformat = config.getProperty("processing","Destination_Type").upper()
    fullmanifest = {"source":[],"masks":[],"processed":[]}
    maskpath = os.path.join(scratchdir,"Masks")
    maskext=config.getProperty("photogrammetry","mask_ext")
    isMasked = manifest[project]["maskmode"] !=0
    for f in files:
        basename_with_ext = os.path.split(f)[1]
        basename = os.path.splitext(basename_with_ext)[0]
        if not os.path.exists(os.path.join(basedir,basename_with_ext)):
            get_logger().warning("Did not find Original file: %s in %s. Manifest verification will fail.",basename_with_ext,basedir)
            foundallfiles &= False
        elif foundallfiles:
            #check to see if the processed version of the original image exists in the expected location, and if so, inventory it.
            fullmanifest["source"].append(os.path.join(basedir,basename_with_ext))
            processedpath = os.path.join(scratchdir,"processed")
            if not os.path.exists(os.path.join(processedpath,f"{basename}{destformat}")):
                get_logger().info("Did not find %s  file for %s in %s. Attempting to convert or transfer.",destformat,basename_with_ext,processedpath)
                image_processing.process_image(os.path.join(basedir,basename_with_ext),processedpath,destformat)                   

            processedfile = os.path.join(processedpath,f"{basename}{destformat}")
            fullmanifest["processed"].append(processedfile)
            foundallfiles &= os.path.exists(processedfile)
            if isMasked:
                if not os.path.exists(os.path.join(maskpath,f"{basename}{maskext}")):
                    get_logger().info("Warning: did not find mask for %s in %s. Attempting to make one.", basename_with_ext,maskpath)
                    image_processing.build_masks(processedfile,
                                                 maskpath,
                                                 manifest[project]["maskmode"])
                maskfile = os.path.join(maskpath,f"{basename}{maskext}")
                fullmanifest["masks"].append(maskfile)
                foundallfiles &= os.path.exists(maskfile)
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

        ext = os.path.splitext(event.src_path)[1].upper()
        if event.event_type=="created" and ext in[".CR2",".JPG",".TIF"]:
            fn = os.path.splitext(event.src_path)[0]
            if not fn.endswith('rj'):#Ortery makes two files, one ending in rj, when it imports to the temp folder.
                if not should_prune(event.src_path):
                    last_size = -1
                    current_size = os.path.getsize(event.src_path)
                    while True:
                        time.sleep(1)
                        last_size = current_size
                        current_size = os.path.getsize(event.src_path)
                        get_logger().debug("%s :%s for %s",last_size,current_size,event.src_path)
                        if current_size==last_size:
                            break
                    if current_size >0:    
                        netdrive = Configurator.getConfig().getProperty("watcher","networkdrive")
                        transferscripts.transferToNetworkDirectory(netdrive, [event.src_path])
                        fn = Path(event.src_path).name
                        global MANIFEST
                        MANIFEST.addFile(fn)
                        get_logger().info("Added file to manifest: %s",fn)


class WatcherRecipientHandler(FileSystemEventHandler):
    """This is the handler class for the watcher. It handles any filesystem event that happens while the watcher is running.
    It extends Watchdog.FilesystemEventHandler."""
    @staticmethod
    def process_incomming_file(eventpath):
        config = Configurator.getConfig()
        if eventpath.endswith("_manifest.txt"):
            build_model_from_manifest(eventpath)
        else:
            scratchdir = config.getProperty("watcher","temp_scratch")
            maskpath = os.path.join(scratchdir,config.getProperty("photogrammetry","mask_path"))
            desttype =config.getProperty("processing","Destination_Type")
            imagetypes = [".CR2",".JPG",".TIF"]
            eventpathext = os.path.splitext(eventpath)[1].upper()
            processedpath = os.path.join(scratchdir,"processed")
            basename_with_ext = os.path.split(eventpath)[1]
            basename = os.path.splitext(basename_with_ext)[0]
            
            if eventpathext in imagetypes and eventpathext != desttype.upper():
                image_processing.process_image(eventpath,processedpath,desttype)
            elif eventpathext ==desttype.upper():
                copy_file_to_dest([eventpath],processedpath, False)
            else:
                print("Unrecognized filetype: {eventpathext}")
                return
            defmask = config.getProperty("processing","ListenerDefaultMasking")
            mode = MaskingOptions.friendlyToEnum(defmask)
            if mode !=  MaskingOptions.NOMASKS.value:
                image_processing.build_masks(os.path.join(processedpath,f"{basename}{desttype}"),maskpath,mode)


    @staticmethod
    def on_any_event(event):
        """Event handler for any file system event. When an event of the type file created happens, if a CR2 file is created, the files will be processed and converted to TIF
        if a manifest file is created, a model will be built based on the manifest's files.
        Parameters:
        -------------------
        event: a watchdog.event from the watchdog library.
        """
        if event.event_type=="created":
            ext = os.path.splitext(event.src_path)
            if len(ext) <2:
                return
            extlist = [".jpg",".cr2",".tif",".txt",".json"]
            if ext[1].lower() in extlist:
                last_size = -1
                current_size = os.path.getsize(event.src_path)
                while True:
                    time.sleep(1)
                    last_size = current_size
                    current_size = os.path.getsize(event.src_path)
                    print(f"{last_size} :{current_size} for {event.src_path}")
                    
                    if current_size==last_size:
                        break
                if current_size != 0:
                    WatcherRecipientHandler.process_incomming_file(event.src_path)

class Watcher:
    """These classes are part of a filesystem watcher which watches for the 
    appearance of a manifest file in the desired directory, then builds a model with the pictures
    
    Methods:
    ------------------------
    __init__(self,directory):initializes the class to watch a particular directory, configurabe in config.json.
    run(): makes a watcherHandler object and waits for it to intercept filesystem events.
    """
    def __init__(self, watchdir:str, isSender = False, projectname=""):
        self.observer = Observer()
        self.watched_dir = watchdir
        self.isSender = isSender
        self.projectname = projectname
        self.maskmode = 0
        self.stoprequest = False

    def run(self):
        """Manages the threads for the watcher scripts. Basically schedules threads to listen for changes to a folder on the filesystem
        and sleeps until there is either an exception or the user presses the F key. Note that this non-blocking user input check is 
        Windows Only and will have to be fixed to make this script mac/linux compatible. When the user hits the F key, if they are running
        the listen_and_send scripts, it will send a manifest of the files that were transfered."""

        if not self.isSender:
            handler = WatcherRecipientHandler()
            
        else:
            global MANIFEST
            MANIFEST = Manifest(self.projectname, self.maskmode)
            handler = WatcherSenderHandler()
        self.observer.schedule(handler,self.watched_dir,recursive=True)
        self.observer.start()
        try:
            get_logger().info("Waiting for pictures to process.")
            listening=True
            print("Type F to Finish.")           
            while listening :
                time.sleep(1)
                if msvcrt.kbhit() or self.stoprequest:
                    if self.stoprequest or (msvcrt.getch()=='F'):
                        listening=False
                        self.observer.stop()
                        self.stoprequest=False
        except Exception as e:
            get_logger().error("Halting threads due to exception %s",e)
            self.observer.stop()
        finally:
            get_logger().info("Watcher stopping.")
            self.observer.join()
        if  self.isSender and MANIFEST:
           
            manifestpath=MANIFEST.finalize(".").resolve()
            get_logger().info("Sending manifest %s",manifestpath)
            netdrive = Configurator.getConfig().getProperty("watcher","networkdrive")
            transferscripts.transferToNetworkDirectory(netdrive,[manifestpath])

def listen_and_send(args):
    """Listens for incoming cr2 files and sends them to the network drive to be converted to tifs and then processed"

    Parameters:
    --------------------------
    args:Argument object from the command line with the following attributes: inputdir: a directory to listen on, in this case, the palce where
    pics will be created by the photography software . 
    Projectname: a projectname to be written to the manifest which will be sent when pics are finalized.
    """
    inputdir =  Configurator.getConfig().getProperty("watcher","listen_and_send")
    global PRUNE
    PRUNE = args.prune
    masktype = int(args.maskoption) if args.maskoption else 0
    if not os.path.exists(inputdir):
        print(f"Cannot listen on a directory that does not exist: {inputdir}")
    watcher = Watcher(inputdir,isSender=True, projectname = args.projectname)
    watcher.maskmode = masktype

    watcher.run()
        
def watch_and_process_cmd(args):
    """function that controls the watcher script which initializes a build when pictures and a manifest are added to a specified directory.
    Parameters:
    ---------------
    args: Argument object handed from the command line which has the following attributes:
    inputdir: a directory to listen on. If this is not specified in the command line, the watcher->listen directory 
    will be used from config.json.
    """
    inputdir = args.inputdir if args.inputdir else Configurator.getConfig().getProperty("watcher","listen_directory")
    scratchdir = Configurator.getConfig().getProperty("watcher","temp_scratch")
    if not os.path.exists(scratchdir):
        os.mkdir(scratchdir)
    if not inputdir:
        print("Input Directory needed if not provided in config.json. (Check Watcher:Listen_Directory)")
        return
    watcher = Watcher(inputdir,isSender=False)
    watcher.run()

def build_snapshot(projname,basefolder):

    fn  = get_export_filename(projname,"obj")
    objpath = Path(basefolder,"output",f"{fn}.obj")
    if objpath.exists():
        MeshlabHelpers.snapshot(objpath,0.0,0.0,0.0,True)

#This script contains the full automation flow and is triggered by the watcher
def build_model_from_manifest(manifestfile:str):
    """Builds a model from the files listed in a text file manifest.

    Parameters:
    -----------
    manifest: A path to a text file manifest with a comma seperated list of paths to image files.
    """
    config = Configurator.getConfig()
    filestoprocess=[]
    parentdir= os.path.abspath(os.path.join(manifestfile,os.pardir))
    manifest = {}
    with open(manifestfile,"r",encoding="utf-8") as f:
        manifest = json.load(f)
    projname = next(iter(manifest))
    masktype = manifest[projname]["maskmode"] = MaskingOptions(manifest[projname]["maskmode"]) or MaskingOptions.friendlyToEnum(config.getProperty("processing","ListenerDefaultMasking"))
    sid = statistics.getStatistics().timeEventStart(Statistic_Event_Types.EVENT_TAKE_PHOTO,
                                                        manifest[projname]["photo_start_time"])
    statistics.getStatistics().timeEventEnd(sid,
                                             manifest[projname]["photo_end_time"])
    succeeded, filestoprocess = verifyManifest(manifest, parentdir)

    if succeeded:
        #if the configured project directory doesn't exist, make it.
        project_base =os.path.join(config.getProperty("watcher","project_base"))
        if not os.path.exists(project_base):
            os.mkdir(project_base)
        #setup project directories.
        project_folder = os.path.join(project_base,projname)
        if not os.path.exists(project_folder):
            os.mkdir(project_folder)
        masks = os.path.join(project_folder,config.getProperty("photogrammetry","mask_path"))
        copy_file_to_dest(filestoprocess["masks"],masks, True)
        processed= os.path.join(project_folder,"processed")
        copy_file_to_dest(filestoprocess["processed"],processed, True)
        source = os.path.join(project_folder,"source")
        copy_file_to_dest(filestoprocess["source"],source, True)
        build_model(projname,processed,project_folder,masktype,snapshot=True)

                    
def build_model(jobname,inputdir,outputdir,mask_option=MaskingOptions.NOMASKS,snapshot=False):
    """Given a folder full of pictures, this function builds a 3D Model.

    Parameters:
    ------------------
    jobname: the name of the model to be built.
    inputdir: a folder full of pictures in either CR2 or TIF format.
    outputdir: The folder in which the model will be placed along with its intermediary files.
    config: the full contents of config.json.
    nomasks: boolean value determining whether to build masks or not.
    """
    config = Configurator.getConfig()
    try:
        from photogrammetry import MetashapeTools
        if not os.path.exists(outputdir):
            os.mkdir(outputdir)

        processedpath = inputdir 
              
        with os.scandir(inputdir) as it:
            for f in it:
                if os.path.isfile(f):
                    if f.name.upper().endswith(config.getProperty("processing","Source_Type")):
                        tifpath = os.path.join(outputdir,config.getProperty("processing","Destination_Type")[1:])
                        if not os.path.exists(tifpath):
                            os.mkdir(tifpath)
                        image_processing.process_image(f.path,tifpath,config.getProperty("processing","Destination_Type"))
                        processedpath = tifpath       
        if mask_option != MaskingOptions.NOMASKS:
            maskpath = os.path.join(outputdir,config.getProperty("photogrammetry","mask_path"))
            if not os.path.exists(maskpath):
                os.mkdir(maskpath)
                image_processing.build_masks(processedpath,maskpath,mask_option)
        MetashapeTools.build_basic_model(photodir=processedpath,
                                         projectname=jobname,
                                         projectdir=outputdir,
                                         maskoption=mask_option)
        if snapshot:
            build_snapshot(jobname,outputdir)
        statistics.getStatistics().logReport()
        statistics.destroyStatistics()
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
    maskoption = int(args.maskoption)
    build_model(job,photoinput,outputdir, MaskingOptions(maskoption))
    


def transfer_to_network_folder(args):
    """This script is for transfering files from the ortery computer to the network drive. 
    
    It copies the files to the drive specified in config.json under watcher->networkdrive. 
    Then, as a final step, it leaves a manifest of the files it copied as a comma seperated list entitled "Files_To_Process.txt." 
    This file will be used as a signal that the sending is complete by any machine listening for changes on the folder.

    Parameters:
    ------------
    args: an arguments object with the following attributes: imagedirectory (a directory of images to transfer), 
    jobname (the name of the job associated with these)
    p: a flag that is true or false, which determines whether these pictures need to be pruned. The ortery takes too many pictures for 
    some views. THis makes the process take longer than needed and adds sources of error at certain angles. To fix it, we can delete a fraction
    of the pictures from each photography angle. The configuration for this is located under config.json->transfer->ortery
."""
    inputdir = args.imagedirectory
    jobname = args.jobname
    def getFileCreationTime(item):
        return os.path.getctime(item)
    fs=[os.path.join(inputdir,f) for f in os.listdir(inputdir) if f.endswith("cr2")]
    filestocopy = sorted(fs,key=getFileCreationTime)
    if args.p: #if the pics need to be pruned...
       filestocopy= transferscripts.pruneOrteryPics(filestocopy,_CONFIG["ortery"])
    transferto=os.path.join(_CONFIG["watcher"]["networkdrive"],jobname)
    transferscripts.transferToNetworkDirectory(transferto, filestocopy,)
    manifest  = os.path.join(transferto,"Files_to_Process.txt")
    with open(manifest,"w") as f:
        f.write(",".join(filestocopy))


def build_masks_cmd(args):
    """Wrapper script for building masks from contents of a folder using a photoshop droplet.
    Parameters:
    -----------
    args: an object containing attributes which get passed in from the command line.  These are:
    inputdir: the directory of pictures that need to be masked in TIF format.
    output: the directory where the masks need to get copied when the masking is done.
    """
    input = args.inputdir
    output = args.outputdir
    image_processing.build_masks(input,output,int(args.maskoption))

def convert_raw_to_format_cmd(args):
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
                        image_processing.convert_CR2_to_DNG(os.path.join(f),outputdir)
                    if args.tif:
                        image_processing.convert_CR2_to_TIF(os.path.join(f),outputdir)
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


if __name__=="__main__":
    _CONFIG = load_config()
    parser = argparse.ArgumentParser(prog="photogrammetryScripts")
    subparsers = parser.add_subparsers(help="Sub-command help")
    convertprocessor = subparsers.add_parser("convert", help=" Convert a Raw file to another format ")
    convertprocessor.add_argument("--dng",help="Converts RAW to dng type", action="store_true")
    convertprocessor.add_argument("--tif", help = "Convert RAW to tif type", action="store_true")
    convertprocessor.add_argument("--jpg", help="Converts TIF to jpg.", action="store_true")
    convertprocessor.add_argument("imagedirectory", help="Directory of raw files to operate on.", type=str)
    convertprocessor.add_argument("outputdirectory", help="Directory to put the output processed files.", type=str)
    convertprocessor.set_defaults(func=convert_raw_to_format_cmd)

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
    photogrammetryparser.add_argument("--maskoption", type = str, choices=["0","1","2","3","4"], help = "How do you want to build masks:0 = no masks,\
                                    1 = Photoshop droplet(context aware select), \
                                    2 = Photoshop droplet (magic wand), \
                                    3 = Canny Edge detection algorithm \
                                    4 = Grayscale Thresholding",
                                    default=0)

    photogrammetryparser.set_defaults(func=build_model_cmd)

    watcherparser = subparsers.add_parser("watch", help="Watch for incoming files in the directory configured in JSON and build a model out of them.")
    watcherparser.add_argument("--inputdir", help="Optional input directory to watch. The watcher will watch config:watcher:listen_directory by default.", default="")
    watcherparser.set_defaults(func=watch_and_process_cmd)      

    listensendparser = subparsers.add_parser("listenandsend", help="listen for new cr2 files in the specified subdirectory and send them to the network drive, recording them in a manifest.")
    listensendparser.add_argument("projectname", help="Optional input directory to watch. The watcher will watch config:watcher:listen_directory by default.", default="")
    listensendparser.add_argument("--inputdir", help="Optional input directory to watch. The watcher will watch config:watcher:listen_directory by default.", default="")
    listensendparser.add_argument("--maskoption", type = str, choices=["0","1","2","3","4"], 
                            help = "How do you want to build masks:0 = no masks,\
                                    1 = Photoshop droplet(context aware select), \
                                    2 = Photoshop droplet (magic wand), \
                                    3 = Canny Edge detection algorithm \
                                    4 = Grayscale Thresholding",
                            default=0)
    listensendparser.add_argument("--prune", action="store_true", help="If this was taken on the ortery, and you would like to prune certain rounds down to a desired # of pics, pass in this flag and configure the 'pics_per_cam' under ortery in config.json.")
    listensendparser.set_defaults(func=listen_and_send)    

    maskparser = subparsers.add_parser("mask", help="Build Masks for files in a folder using a photoshop droplet.")
    maskparser.add_argument("inputdir", help="Photos to mask")
    maskparser.add_argument("outputdir",help="location to store masks")   
    maskparser.add_argument("--maskoption", type = str, choices=["0","1","2","3","4"], 
                            help = "How do you want to build masks:0 = no masks,\
                                    1 = Photoshop droplet(context aware select), \
                                    2 = Photoshop droplet (magic wand), \
                                    3 = Canny Edge detection algorithm \
                                    4 = Grayscale Thresholding",
                            default=0)

    maskparser.set_defaults(func=build_masks_cmd)


    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()

