from processing import image_processing
from transfer import transferscripts
import math
import shutil
import rawpy
import PIL
import msvcrt
import os.path, json, argparse
import time
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from util import util

#Global Variables
#because the callback methods are static for the watchers, we need a place to store the manifest of the files they are transfering.
MANIFEST = None
#This is the config file. I'm storing it in a global variable so I don't have to pass it or load it from disk constantly.
CONFIG = {}
#prune is a boolean on whether the listener should prune pictures from the ortery or not. Probably ought to come up with
# a non global var way of doing this.
PRUNE = False
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
    def __init__(self, projectname, maskmode):
        self.sentfiles = []
        self.projectname = projectname
        self.maskmode = maskmode
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
        outputjson = {self.projectname:
                      {    "maskmode":self.maskmode,
                          "files":self.sentfiles}}
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
    scratchdir = CONFIG["watcher"]["temp_scratch"]
    foundallfiles=True
    project = next(iter(manifest))
    files = manifest[project]["files"]
    destformat = CONFIG["processing"]["Destination_Type"].upper()
    fullmanifest = {"source":[],"masks":[],"processed":[]}
    maskpath = os.path.join(scratchdir,"Masks")
    maskext=CONFIG["photogrammetry"]["mask_ext"]
    isMasked = manifest[project]["maskmode"] !=0
    for f in files:
        basename_with_ext = os.path.split(f)[1]
        basename = os.path.splitext(basename_with_ext)[0]

        sourceformat = os.path.splitext(basename_with_ext)[1]
        if not os.path.exists(os.path.join(basedir,basename_with_ext)):
            print(f"Warning: did not find Original file: {basename_with_ext} in {basedir}")
            foundallfiles &= False
        else:
            #check to see if the processed version of the original image exists in the expected location, and if so, inventory it.
            fullmanifest["source"].append(os.path.join(basedir,basename_with_ext))
            processedpath = os.path.join(scratchdir,"processed")
            if not os.path.exists(os.path.join(processedpath,f"{basename}{destformat}")):
                print(f"Warning: did not find {destformat} file for {basename_with_ext} in {processedpath}")
                image_processing.process_image(os.path.join(basedir,basename_with_ext),processedpath,CONFIG["processing"])                   

            processedfile = os.path.join(processedpath,f"{basename}{destformat}")
            fullmanifest["processed"].append(processedfile)
            foundallfiles &= os.path.exists(processedfile)
            if isMasked:
                if not os.path.exists(os.path.join(maskpath,f"{basename}.{maskext}")):
                    print(f"Warning: did not find mask for {basename_with_ext} in {maskpath}")
                    image_processing.build_masks(processedfile,
                                                 maskpath,
                                                 manifest[project]["maskmode"],
                                                 CONFIG["processing"])
                maskfile = os.path.join(maskpath,f"{basename}.{maskext}")
                fullmanifest["masks"].append(maskfile)
                foundallfiles &= os.path.exists(maskfile)
  
    return foundallfiles,fullmanifest
def should_prune(filename: str)->bool:
    """Takes a file name and figures out based on the number in it whether the picture should be sent or not and added to the manifest or not. It assumes files are named ending in a number and that
    this is sequential based on when the camera took the picture.
    Parameters
    -----------------
    filename: The filename in question.
    
    returns: True or false based on whether the file ought to be omitted.
    """
    if not PRUNE:
        return 
    shouldprune = False
    numinround = CONFIG["ortery"]["pics_per_revolution"]
    numcams = len(CONFIG["ortery"]["pics_per_cam"].keys())
    basename_with_ext = os.path.split(filename)[1]
    fn = os.path.splitext(basename_with_ext)[0]
    try:
        t = re.match(r"[a-zA-Z]*_*(\d+)$",fn)
        filenum = int(t.group(1)) #ortery counts from zero.
        camnum = int(filenum/numinround)+1
        picinround = filenum%(numinround)+1
        expected = CONFIG["ortery"]["pics_per_cam"][str(camnum)]
        print(f"{fn} is pic number {picinround} of camera {camnum}. The expected number in this round is {expected}")
        if expected < numinround:
            invert = False
            if (numinround-expected)/numinround <0.5:
                divisor = round(numinround/(numinround-expected))
            else:
                divisor = round(numinround/expected)
                invert = True
            if (picinround %divisor==0) and invert is False:
                shouldprune=True
                print("Prune Me")
            elif (picinround % divisor != 0) and invert is True:
                shouldprune = True
                print("Prune me")
            else:
                print("Don't Prune Me.")
    except AttributeError:
        print(f"Filename {fn} were not in format expected: [a-zA-Z]*_*\\d+$.xxx . Forgoing pruning.")
        shouldprune = False
    finally:
        return shouldprune
    
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
                        time.sleep(3)
                        last_size = current_size
                        current_size = os.path.getsize(event.src_path)
                        print(f"{last_size} :{current_size} for {event.src_path}")
                
                        if current_size==last_size:
                            break
                    if current_size >0:    
                        transferscripts.transferToNetworkDirectory(CONFIG["watcher"]["networkdrive"], [event.src_path])
                        global MANIFEST
                        MANIFEST.addFile(event.src_path)
                        print(f"added to manifest: {event.src_path}")

class WatcherRecipientHandler(FileSystemEventHandler):
    """This is the handler class for the watcher. It handles any filesystem event that happens while the watcher is running.
    It extends Watchdog.FilesystemEventHandler."""
    @staticmethod
    def process_incomming_file(eventpath):

        if eventpath.endswith("_manifest.txt"):
            build_model_from_manifest(eventpath)
        else:
            scratchdir = CONFIG["watcher"]["temp_scratch"]
            maskpath = os.path.join(scratchdir,CONFIG["photogrammetry"]["mask_path"])
            desttype = CONFIG["processing"]["Destination_Type"]
            imagetypes = [".CR2",".JPG",".TIF"]
            eventpathext = os.path.splitext(eventpath)[1].upper()
            processedpath = os.path.join(scratchdir,"processed")
            basename_with_ext = os.path.split(eventpath)[1]
            basename = os.path.splitext(basename_with_ext)[0]
            
            if eventpathext in imagetypes and eventpathext != desttype.upper():
                image_processing.process_image(eventpath,processedpath,CONFIG["processing"])
            elif eventpathext ==desttype.upper():
                util.copy_file_to_dest([eventpath],processedpath, False)
            else:
                print("Unrecognized filetype: {eventpathext}")
                return
            image_processing.build_masks_with_droplet(os.path.join(processedpath,f"{basename}{desttype}"),maskpath,CONFIG["processing"])

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
                    
                    if current_size==last_size and current_size != 0:
                        break
                WatcherRecipientHandler.process_incomming_file(event.src_path)

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
        self.maskmode = 0

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
            listening=True
            print("Type F to Finish.")           
            while listening :
                time.sleep(5)
                if msvcrt.kbhit():
                    if msvcrt.getch()==b'F':
                        listening=False
                        self.observer.stop()
        except Exception as e:
            print(f"Halting threads due to exception {e}")
            self.observer.stop()
        finally:
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
    global PRUNE
    PRUNE = args.prune
    masktype = int(args.maskoption) if args.maskoption else 0
    if not os.path.exists(inputdir):
        print(f"Cannot listen on a directory that does not exist: {inputdir}")
    watcher = Watcher(inputdir,isSender=True, projectname = args.projectname)
    watcher.maskmode = masktype

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
    scratchdir = CONFIG["watcher"]["temp_scratch"]
    if not os.path.exists(scratchdir):
        os.mkdir(scratchdir)
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
    projname = next(iter(manifest))
    masktype = manifest[projname]["maskmode"]
    start = time.perf_counter()
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
        masks = os.path.join(project_folder,CONFIG["photogrammetry"]["mask_path"])
        util.copy_file_to_dest(filestoprocess["masks"],masks, True)
        processed= os.path.join(project_folder,"processed")
        util.copy_file_to_dest(filestoprocess["processed"],processed, True)
        source = os.path.join(project_folder,"source")
        util.copy_file_to_dest(filestoprocess["source"],source, True)
        stop = time.perf_counter()
        verify_time = stop-start
        start = time.perf_counter()
        build_model(projname,processed,project_folder,CONFIG,masktype)
        stop = time.perf_counter()
        build_time = stop-start
        print(f"Time to build masks and convert files: {verify_time}\n Time to Build Model: {build_time} seconds.")

        
def build_model(jobname,inputdir,outputdir,config,mask_option=0):
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
                        tifpath = os.path.join(outputdir,"tif")
                        if not os.path.exists(tifpath):
                            os.mkdir(tifpath)
                        image_processing.process_image(f.path,tifpath,config['processing'])
                        processedpath = tifpath       
        if mask_option != util.MaskingOptions.NOMASKS:
            print("Building Masks...")
            maskpath = os.path.join(outputdir,config["photogrammetry"]["mask_path"])
            if not os.path.exists(maskpath):
                os.mkdir(maskpath)
                image_processing.build_masks(processedpath,maskpath,mask_option,config["processing"])      
        else:
            config["photogrammetry"].pop("mask_path")
        print(f"Building Model {jobname} with photos in {processedpath} and outputting in {outputdir}")
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
    maskoption = args.maskoption
    build_model(job,photoinput,outputdir,CONFIG,maskoption)
    


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
if __name__=="__main__":
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
    photogrammetryparser.add_argument("--maskoption", type = int, choices=["0","1","2"], help = "How do you want to build masks:0 = no masks, 1 = photoshop droplet, 2 = arbitrary line", default=1)

    photogrammetryparser.set_defaults(func=build_model_cmd)

    watcherparser = subparsers.add_parser("watch", help="Watch for incoming files in the directory configured in JSON and build a model out of them.")
    watcherparser.add_argument("inputdir", help="Optional input directory to watch. The watcher will watch config:watcher:listen_directory by default.", default="")
    watcherparser.set_defaults(func=watch_and_process)      

    listensendparser = subparsers.add_parser("listenandsend", help="listen for new cr2 files in the specified subdirectory and send them to the network drive, recording them in a manifest.")
    listensendparser.add_argument("inputdir", help="Optional input directory to watch. The watcher will watch config:watcher:listen_directory by default.", default="")
    listensendparser.add_argument("projectname", help="Optional input directory to watch. The watcher will watch config:watcher:listen_directory by default.", default="")
    listensendparser.add_argument("--maskoption", type = str, choices=["0","1","2"], help = "How do you want to build masks:0 = no masks, 1 = photoshop droplet, 2 = arbitrary line", default=0)
    listensendparser.add_argument("--prune", action="store_true", help="If this was taken on the ortery, and you would like to prune certain rounds down to a desired # of pics, pass in this flag and configure the 'pics_per_cam' under ortery in config.json.")
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

