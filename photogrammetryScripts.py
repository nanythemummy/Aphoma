


import os.path, json, argparse
from os import makedirs
import time
from pathlib import Path
from queue import Queue
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from util.ErrorCodeConsts import ErrorCodes
from util.util import MaskingOptions, copy_file_to_dest, should_prune, get_export_filename
from util.PipelineLogging import getLogger as getGlobalLogger
from util.Configurator import Configurator
from util.InstrumentationStatistics import InstrumentationStatistics as statistics
from util.InstrumentationStatistics import Statistic_Event_Types
from processing import image_processing
from transfer import transferscripts
from tasks import MetashapeTasks,BlenderTasks,ConversionTasks,MaskingTasks
from util import MetashapeFileHandleSingleton

from postprocessing import MeshlabHelpers
from util.buildManifest import Manifest


def get_logger():
    return getGlobalLogger(__name__)
#Global Variables
#because the callback methods are static for the watchers, we need a place to store the manifest of the files they are transfering.
MANIFEST = None

#prune is a boolean on whether the listener should prune pictures from the ortery or not. Probably ought to come up with
# a non global var way of doing this.
PRUNE = False

FINISHED = False

#These scripts  takes input and arguments from the command line and delegates them elsewhere.
#For individual transfer scripts see the transfer module, likewise, see the processing module for processing scripts.




def verifyManifest(tq:Queue,manifest:dict, basedir:Path,mode:MaskingOptions, report_stats = True, cancelevent:threading.Event = None):
    """Goes through a dictionary taken from a manifest file on disk and checks to see that all of
    the RAW files are there, all the mask files have been made, and all of the tifs have been made.
    
    Parameters"
    ---------------
    manifest: A dict containing a list of files of the format projectname:[filenames]
    basedir: the base directory to look for the rawfiles, tifs, and masks, which are in subfolders called tifs and masks.
    
    returns: succeeded, full_manifest, where succeeded is true if all the masks and tifs and raw files expected were found, and 
    manifest contains each of these files and their full paths in the format {"raw":[],"tif":[],"masks":[]}"""

    #check to see if all the masks and tifs have been made for this manifest.
    get_logger().info("Verifying")
    config = Configurator.getConfig()
    scratchdir = config.getProperty("watcher","temp_scratch")
    processedpath = Path(scratchdir,"processed")
    foundallfiles=True
    project = manifest["projectname"]
    files = [Path(basedir,Path(f).name) for f in manifest["files"]]
    desttypes = config.getProperty("processing","Destination_Type") #strips out the leading dot on the extension.
    fullmanifest = {"source":[],"masks":[],"project":project}
    for d in desttypes:
        fullmanifest[d[1:]]=[]
    maskpath = Path(processedpath,"Masks")
    maskext=config.getProperty("photogrammetry","mask_ext")
    is_masked = mode !=MaskingOptions.NOMASKS
    for f in files:
        if f.exists() and f.is_file():
            #check to see if the processed version of the original image exists in the expected location, and if so, inventory it.
            fullmanifest["source"].append(f)
            for t in desttypes:
                destsubfolder = t[1:]
                subfolder = Path(processedpath,destsubfolder)
                processedfile = Path(subfolder,f"{f.stem}{t}")
                if destsubfolder not in fullmanifest.keys():
                    fullmanifest[destsubfolder]=[]
                if not processedfile.exists():
                    if f.suffix==t: #ie, we added a file that is one of the destination types,
                        copy_file_to_dest([f],subfolder)
                    else:
                        get_logger().info("Did not find %s  file for %s in %s. Attempting to convert or transfer.",t,f.stem,processedpath)
                        tq=setupConversionTasks(tq,[f],processedpath,False)     
                fullmanifest[destsubfolder].append(processedfile)
            if is_masked:
                maskfile =Path(maskpath,f"{f.stem}{maskext}")
                if not maskfile.exists():
                    get_logger().info("Warning: did not find mask for %s in %s. Attempting to make one.", f.name,maskpath)
                    masksource = Path(processedpath,"jpg",f"{f.stem}.jpg")
                    tq=setupMaskingTasks(tq,[masksource],processedpath,mode)
                fullmanifest["masks"].append(maskfile)
        else:
            get_logger().warning("Did not find Original file: %s in %s. Manifest verification will fail.",f.name,basedir)
            foundallfiles = False
    executeTaskQueue(tq,True,False,cancelevent)
    return foundallfiles,fullmanifest, tq

class FSSenderHandler(FileSystemEventHandler):
    """Listen in the specified directory for cr2 files. It extends Watchdog.FilesystemEventHandler"""
    def __init__(self, cancel_event:threading.Event, manifest_queue:Queue, shouldprune = False ):
        self.should_pune = shouldprune
        self.cancel_event = cancel_event
        self.manifest_queue = manifest_queue
        super().__init__()
    
    def on_any_event(self,event):
        """Event handler for any file system event. When an event of the type file created happens, if a CR2 file is created, the files will be processed and converted to TIF
        if a manifest file is created, a model will be built based on the manifest's files.
        Parameters:
        -------------------
        event: a watchdog.event from the watchdog library.
        """

        eventpath = Path(event.src_path)
        allowableextensions = Configurator.getConfig().getProperty("processing","Source_Type")
        if event.event_type=="created" and eventpath.suffix in allowableextensions:
            fn = eventpath.name
            if not fn.endswith('rj'):#Ortery makes two files, one ending in rj, when it imports to the temp folder.
                if not should_prune(eventpath):
                    last_size = -1
                    current_size = eventpath.stat().st_size
                    while True:
                        time.sleep(1)
                        last_size = current_size
                        current_size = eventpath.stat().st_size
                        get_logger().debug("%s :%s for %s",last_size,current_size,event.src_path)
                        if current_size==last_size:
                            break
                    if current_size >0:   
                        netdrive = Configurator.getConfig().getProperty("watcher","networkdrive")
                        transferscripts.transferToNetworkDirectory(netdrive, [event.src_path])
                        fn = Path(event.src_path).name
                        self.manifest_queue.put(fn)


class FSWatcherHandler(FileSystemEventHandler):
    def __init__(self, eventqueue: Queue, cancel_event):
        self._event_queue = eventqueue
        self.cancel_event = cancel_event
        super().__init__()

   
    def process_incomming_file(self,eventpath):
        
        config = Configurator.getConfig()
        scratchdir = config.getProperty("watcher","temp_scratch")
        desttype =config.getProperty("processing","Destination_Type")
        defmask = config.getProperty("processing","ListenerDefaultMasking")
        buildtype = config.getProperty("processing","Build_From_Format")
        mode = MaskingOptions.friendlyToEnum(defmask)
        if str(eventpath).endswith("_manifest.json"):
            buildModelFromManifest(self._event_queue,eventpath,mode)
        else:
            e = Path(eventpath)
            eventpathext = Path(eventpath).suffix.lower()
            processedpath = Path(scratchdir,"processed")
            predictedfinal = Path(processedpath,buildtype[1:],f"{e.stem}{buildtype}")
            filedest = Path(processedpath,eventpath.suffix[1:])
            if eventpathext.lower() not in desttype or len(desttype)>0: 
                #basically run this if there are multiple conversion types and the input is one of them or if the input is not in the list of output types.
                setupConversionTasks(self._event_queue,[e],processedpath, False)
                if eventpathext.lower() in desttype:
                    copy_file_to_dest([eventpath],filedest, False)
                
            else:
                copy_file_to_dest([eventpath],filedest, False)
            
            if mode !=  MaskingOptions.NOMASKS.value:
               setupMaskingTasks(self._event_queue,[predictedfinal],processedpath,mode)
                    
            executeTaskQueue(self._event_queue,True,False,self.cancel_event)

   
    def on_any_event(self,event):
        """Event handler for any file system event. When an event of the type file created happens, if a CR2 file is created, the files will be processed and converted to TIF
        if a manifest file is created, a model will be built based on the manifest's files.
        Parameters:
        -------------------
        event: a watchdog.event from the watchdog library.
        """
        if event.event_type=="created":
            newpath = Path(event.src_path)
            ext = newpath.suffix
            if ext.upper() in [".JPG",".CR2",".TIF",".NEF",".JSON"]:
                last_size = -1
                current_size = newpath.stat().st_size
                while True and not self.cancel_event.is_set():
                    time.sleep(3)
                    last_size = current_size
                    current_size = newpath.stat().st_size
                    print(f"{last_size} :{current_size} for {newpath}")
                    if current_size==last_size:
                        break
                if current_size != 0:
                    self.process_incomming_file(newpath)



def startWatcher(watchdir:Path, cancelevent:threading.Event = None):
    """startWatcher: This is the function that the UI calls when the user wants to listen for incomming files on a network directory to build a model.
    I'm debating whether to just wrap it in a class like I did with Photosender.

        Parameters:
        ------------
        watchdir: A path to watch for incoming files.
        cancelevent: A threading.event that gets set when the user presses a cancel button.
        
    """
    eq = Queue()
    fshandler = FSWatcherHandler(eq, cancelevent)
    fsobserver = Observer()
    fsobserver.schedule(fshandler,watchdir,recursive=True)
    fsobserver.start()
    while not cancelevent.is_set():
        time.sleep(3)
    fsobserver.stop()
    fsobserver.join()


class PhotoSender:
    """This class waits for files to appear in a specified directory, and if they are image files, it sends them to a network drive, based on whether
    they should be pruned based on the pruning algorithm and whether they are files that can be processed by the system. It adds files that arrive
    to a manfest which is set to the network drive when the photography is done or the user cancels via the UI.
    It acts as a wrapper for a Watchdog:Observer class.

    Methods:
    ------------------------
    __init__(self,directory):initializes the class to watch a particular directory, configurabe in config.json.
    run(): makes a watcherHandler object and waits for it to intercept filesystem events.
    """

    def __init__(self,  watchdir:Path, cancelevent:threading.Event, projectname:str="",  shouldPrune:bool=False):
        """Photosender::__init__ initializes a Photosender object. This acts as a wrapper class for Watchdog:Observer. It has the logic which launches threads to watch for incomming calls on the filesystem
        and it also checks the manifest queue to see if there are any new files in the manifest queue to add to the manifest. It sends the manifest when finished.
        It should be run on the ortery computer or a computer attached to a camera taking pictures.

        Parameters:
        ------------
        watchdir: A path to watch for incoming files.
        cancelevent: A threading.event that gets set when the user presses a cancel button or anything else.
        shouldPrune: should not transfer every xth picture according to the pruning tuning in config.json
        
        """
        self.observer = Observer()
        self.watched_dir = watchdir
        self.projectname = projectname
        self.shouldPrune = shouldPrune
        self.stoprequest = False
        self.cancelEvent = cancelevent
        self.finished = False

    def setCancelled(self,isFinished:bool=False):
        """Photosender::setCancelled. sets the cancel threading event, signalling for all threads to halt and for the for loop in run to stop looping. It has a isFinished value
        which should be set if the desired result is that the threads halt AND the manifest get sent to the network drive.
        
        Parameters:
        --------------
        isFinished: Set this boolean to true if the user is done photographing and would like to send the manifest to the processing computer. 
        """
        self.cancelEvent.set()
        self.finished = isFinished

    def run(self):
        """Photosender::Run Manages the threads for the watcher scripts. Basically schedules threads to listen for changes to a folder on the filesystem
        and sleeps until there is either an exception or the user sets the cancel event using the cancel button in the ui. While waiting for new files, it adds
        the previously added files to the manifest. When a cancel event comes through, and if self.finished is True, it sends the manifest, otherwise, the manifest remains unsent
        this is to allow for both a stop and cancel button."""

        manifest = Manifest(self.projectname)
        manifestqueue=Queue()
        handler = FSSenderHandler(self.cancelEvent,manifestqueue,self.shouldPrune)

        self.observer.schedule(handler,self.watched_dir,recursive=True)
        self.observer.start()
        try:
            get_logger().info("Waiting for pictures to process.")
            while not self.cancelEvent.is_set():
                time.sleep(1)
                while not manifestqueue.empty():
                    manifest.addFile(manifestqueue.get())
            self.observer.stop()
            if self.finished:
                manifestpath=manifest.finalize(".").resolve()
                get_logger().info("Sending manifest %s",manifestpath)
                netdrive = Configurator.getConfig().getProperty("watcher","networkdrive")
                transferscripts.transferToNetworkDirectory(netdrive,[manifestpath])
        except Exception as e:
            get_logger().error("Halting threads due to exception %s",e)
            self.observer.stop()
            raise(e)
        finally:
            get_logger().info("Watcher stopping.")
            self.observer.join()
            self.cancelEvent.clear()
            self.finished=False


def buildModelFromManifest(tq:Queue,manifestfile:Path, maskmode:MaskingOptions):
    """buildModelFromManifest: Builds a model from unconverted raw files (if necessary) using the source files found in a json manifest. 
    This gets called by the watcher handler from the ortery and is meant to be used when the masking tasks or conversion tasks are partly done but the model has not
    yet been built because the photography is still underway. When the photography is finished, a manifest is sent inventorying the original files. This builds
    a model from that list.

    Parameters:
    -----------
    tq: a Queue of tasks--this can be partially filled or not filled at all. Needed tasks will be added by the verify manifest function.
    manifest: A pathlib:Path to a text file manifest with a comma seperated list of paths to image files.
    maskmode: An instance of maskingOptions corresponding to the type of masks that ought to be made for each picture in the manifest Pass MaskingOptions:None for none.

    It uses the following config values:
    watcher:project_base -- the user configures a place to store the model and its intermediary files including masks.
    photogrammetry:mask_path -- the subdirectory in which masks will be stored ( or moved from the temp directory where they are placed when they are being made on the fly.)
    processing:Destination_type -- a list of the types of image files that the incoming raw files will be converted to, ie ["jpg","tif"]
    processing:Build_From_Format -- the image format which will be used to build the model. If you don't want a crash, it should be in the list processing:Destination_type.
        
    """
    manifest = {}
    parentdir= Path(manifestfile).parent
    config = Configurator.getConfig()
    with open(manifestfile,"r",encoding="utf-8") as f:
        manifest = json.load(f)
    sid = statistics.getStatistics().timeEventStart(Statistic_Event_Types.EVENT_TAKE_PHOTO, manifest["photo_start_time"])
    statistics.getStatistics().timeEventEnd(sid, manifest["photo_end_time"])
    projname = manifest["projectname"]
    #the following makes sure all conversions are done and all masks are built.
    succeeded, filestoprocess, tq = verifyManifest(tq,manifest, parentdir,maskmode,True)

    if succeeded:
        #if the configured project directory doesn't exist, make it.
        project_base =Path(config.getProperty("watcher","project_base"))
        #setup project directories.
        project_folder = Path(project_base,projname)
        if not project_folder.exists() or not project_folder.is_dir():
            os.makedirs(project_folder)
        masks = Path(project_folder,config.getProperty("photogrammetry","mask_path"))
        copy_file_to_dest(filestoprocess["masks"],masks, True)
        source = Path(project_folder,"source")
        copy_file_to_dest(filestoprocess["source"],source, True)
        for t in config.getProperty("processing","Destination_Type"):
            subfolder = t[1:]
            processed =Path(project_folder,subfolder)
            copy_file_to_dest(filestoprocess[subfolder],processed, True)
        bformat = config.getProperty("processing","Build_From_Format")[1:]
        buildModel(projname,Path(project_folder,bformat),project_folder,maskmode,snapshot=True,tasks=tq)

def executeTaskQueue(taskqueue:Queue,stop_on_empty:bool=True, report_statistics:bool=True, cancelthreadevent:threading.Event = None):
    """executeTaskQueue: Given a task queue, this executes tasks until the queue is empty, running the setup, execute, and exit method on each task. 
    The function returns if an error is encountered on any of these phases. It will also return if the cancelthreadedevent threading event is set--this is set by the 
    cancel button in the UI.

    Parameters:
    ------------------
    task_queue: A queue filled with tasks to execute in the order in which they ought to be executed
    filestoconvert: stop_on_empty--whether the function should return when the queue is empty or continue executing in hopes that more tasks will be added.
    This will be useful if the function is ever multithreaded.
    report_statistics: Reports the time taken for each class of tasks on the end of the run.
    cancelthreadedevent: an event which can be set by another thread. When the event is set, the queue stops being processed. Now, it gets set by the UI.

    """
    get_logger().info("Executing Tasklist.")
    succeeded = True
    global FINISHED
    FINISHED = False
    phase = "setup"
    while(not FINISHED):
        if not taskqueue.empty():
            task = taskqueue.get()
            succeeded,code = task.setup()
            if succeeded:
                phase = "execute"
                succeeded, code =task.execute()
                if succeeded:
                    phase = "exit"
                    succeeded,code = task.exit()
            if not succeeded:
                get_logger().error("Phase %s for Task %s failed with error %s",phase, str(task),ErrorCodes.numToFriendlyString(code))
                FINISHED=True
                break
        
        if stop_on_empty and taskqueue.empty() or (cancelthreadevent and cancelthreadevent.is_set()):
            FINISHED = True
            get_logger().info("Finished the tasklist, ending.")
        
    if report_statistics:
        statistics.getStatistics().logReport()
        statistics.destroyStatistics()
        MetashapeFileHandleSingleton.MetashapeFileSingleton.destroyDoc() #gets created by metashape tasks "align photos."


def setupConversionTasks(task_queue:Queue,filestoconvert:list,basedir:Path,profile_correction:bool=False)->Queue:
    """setupConversionTasks: Given a queue, add tasks needed to convert the specified files to a format that can be used to build a 3d model.

    Parameters:
    ------------------
    task_queue: A queue, populated with tasks that ought to be performed before this one. It can be empty.
    filestoconvert: a list of pathutil:Paths of images.
    basedir: The directory where the model, and psx file, and all intermediary files will be placed.
    profile_correction: whether profile correction ought to be used on these pictures. Only pass True if you used a DSLR camera with a detachable lens.
    This function can be useful if you are using this function to set up a workflow which converts RAW files to TIFs, but do not plan to build a model from the results, 
    Otherwise,the user should exercise caution because attempting to programmatically correct lens
    distortion at conversion time may cause unintended consequences in the final model.

    Additionally, this function relies on the following values in config.json, which can be changed via the UI or via editing the json file.
    Processing:Destination_Type: list of all image  formats that the program should output. Recommended: ["jpg"]. However, some uses may want to convert to jpg and tif for archiving.
    Processing:Source_Type: a list of allowable picture formats that the program can process: currently cr2 (cannon RAW), nef (Nikon RAW), tif, and jpg.
    Processing:Build_From_Format: extension for the format of images the model will be built from. Supported are jpg and tif.
    Returns: the task queue with the new tasks.
    """
    config = Configurator.getConfig()
    conversiontypes = config.getProperty("processing","Destination_Type")
    sourcetypes = config.getProperty("processing","Source_Type")
    desttype = config.getProperty("processing","Build_From_Format")

    if desttype not in conversiontypes:
       get_logger().error(" %s is not in list of conversion formats. Defaulting to JPG.",desttype)
       desttype = ".jpg" #if we misconfigured this, default to jpg.

    for filepath in filestoconvert:
        
        if filepath.is_file() and filepath.suffix.lower() in sourcetypes: #should we bother converting this at all?
            for c in conversiontypes:
                if filepath.suffix.lower() != c:
                    destpath = (Path(basedir,c[1:]))
                    if not Path(destpath).exists():
                        os.makedirs(destpath)
                    if  c == ".jpg":
                        task_queue.put( ConversionTasks.ConvertToJPG({"input":Path(filepath),"output":Path(destpath),"profile_correction":profile_correction}))
                    if c==".tif":
                        task_queue.put( ConversionTasks.ConvertToTIF({"input":Path(filepath),"output":Path(destpath),"profile_correction":profile_correction}))
    return task_queue

def setupMaskingTasks(task_queue:Queue, pathlist:list, basedir:Path, mask_option=MaskingOptions.NOMASKS)->Queue:
    """setupMaskingTasks: Given a queue, add tasks needed to build masks for the images in the passed-in list, using the task corresponding for the
    algorithm specified in mask_optiopns.

    Parameters:
    ------------------
    task_queue: A queue, populated with tasks that ought to be performed before this one. If the model is finished, it can be empty.
    pathlist: a list of pathutil:Paths of images.
    basedir: The directory where the model, and psx file, and all intermediary files will be placed.
    mask_option: the algorithm to use for masking, in the form of a MaskingOptions enumeration.
    
    Additionally, this function relies on the following values in config.json, which can be changed via the UI or via editing the json file.
    photogrammetry:mask_path: this is the subdirectory where the created masks will be stored.

    Returns: the task queue with the new tasks.
    """
    config = Configurator.getConfig()
    if mask_option != MaskingOptions.NOMASKS:
        maskpath = Path(basedir,config.getProperty("photogrammetry","mask_path"))
        if not maskpath.exists():
            os.makedirs(maskpath)
        for f in pathlist:
            if mask_option == MaskingOptions.MASK_CONTEXT_AWARE_DROPLET:
                task_queue.put(MaskingTasks.MaskDroplet({"input":f,"output":maskpath}))
            elif mask_option == MaskingOptions.MASK_AI:
                task_queue.put(MaskingTasks.MaskAI({"input":f,"output":maskpath}))
            else: #use thresholding. 
                task_queue.put(MaskingTasks.MaskThreshold({"input":f,"output":maskpath}))
    return task_queue

def setupPostTasks(task_queue:Queue,jobname:str,basedir:Path, snapshot:bool = True)->Queue:
    """setupPostTasks: Given a queue, add tasks need to process a finished 3d model to that queue, including automated manipulation in blender or meshlab.
    Currently, the only thing this function does is setup the blender snapshot task. This function can be disabled by passing false in the snapshot param.

    Parameters:
    ------------------
    task_queue: A queue, populated with tasks that ought to be performed before this one. If the model is finished, it can be empty.
    jobname: The name of the model (and of the chunk and metashape file)
    basedir: The directory where the model, and psx file, and all intermediary files will be placed.
    snapshot: should this function set up the tasks to make a blender snapshot?

    
    Additionally, this function relies on the following values in config.json, which can be changed via the UI or via editing the json file.
    photogrammetry: output_path: The subdirectory of basedir where the model and its associated files will be stored.
    photogrammetry: export_as: The format of 3d model to export: Supported options are currently  ply and obj

    Returns: the task queue with the new tasks.
    """
    config = Configurator.getConfig()
    outputpath = Path(basedir,config.getProperty("photogrammetry","output_path"))
    objname =  Path(outputpath,get_export_filename(jobname,config.getProperty("photogrammetry","export_as")))
    objfullname = f"{objname}{config.getProperty("photogrammetry","export_as")}"

    if snapshot and config.getProperty("postprocessing","script_directory") != "" and \
    config.getProperty("postprocessing","blender_exec")!="":
        task_queue.put(BlenderTasks.BlenderSnapshotTask({"inputobj":objfullname,"output":outputpath,"scale":True}))
    return task_queue

def setupModelTasks(task_queue:Queue,pathlist:list,jobname:str,inputdir:Path,basedir:Path,mask_option=MaskingOptions.NOMASKS)->Queue:
    """setupModelTasks: Given a queue,add tasks neede to build a model to that queue.

    Parameters:
    ------------------
    task_queue: a queue, populated with tasks needed to build masks if desired and to convert any raw or tif files into jpgs, from which a model will be built.
    pathlist: a list of pathutil:Paths to jpg files which will be used in the model. These need not exist yet, but it is assumed that they will exist by the time model tasks get
    executed.
    jobname: The name of the model (and of the chunk and metashape file)
    inputdir: The directory containing the JPG or TIF files that will be used to build the model.
    basedir: The directory where the model, and psx file, and all intermediary files will be placed.
    mask_option: the method for building the mask as represented in the MaskingOption enumeration class.

    Returns: the task queue with the new tasks.
    """
     
    config = Configurator.getConfig()
    maskpath = Path(basedir,config.getProperty("photogrammetry","mask_path"))
    outputextn = config.getProperty("photogrammetry","export_as")
    paramsfortasks = {"input":inputdir,
                        "output":basedir,
                        "usemasks":mask_option != MaskingOptions.NOMASKS,
                        "maskpath":maskpath,
                        "projectname":jobname,
                        "chunkname":jobname,
                        "photos":pathlist,
                        "extension":outputextn,
                        "conform_to_shape": False
                        }
    task_queue.put(MetashapeTasks.MetashapeTask_AlignPhotos(paramsfortasks))
    task_queue.put(MetashapeTasks.MetashapeTask_ErrorReduction(paramsfortasks))
    task_queue.put(MetashapeTasks.MetashapeTask_DetectMarkers(paramsfortasks))
    task_queue.put(MetashapeTasks.MetashapeTask_AddScales(paramsfortasks))
    task_queue.put(MetashapeTasks.MetashapeTask_BuildModel(paramsfortasks))
    task_queue.put(MetashapeTasks.MetashapeTask_Reorient(paramsfortasks))
    task_queue.put(MetashapeTasks.MetashapeTask_BuildTextures(paramsfortasks))
    task_queue.put(MetashapeTasks.MetashapeTask_ExportModel(paramsfortasks))
    return task_queue

def buildModel(jobname:str,
                inputdir:str,
                basedir:str,
                mask_option=MaskingOptions.NOMASKS,
                snapshot:bool=False,
                tasks:Queue=None, 
                report_statistics:bool=True,
                cancelthreadevent:threading.Event = None):
    """buildModel: Given a folder full of pictures, this function builds a 3D Model.

    Parameters:
    ------------------
    jobname: the name of the model to be built.
    inputdir: a folder full of pictures in either CR2 or TIF format.
    basedir: The folder in which the model will be placed along with its intermediary files.
    mask_option: the type of mask to build for each image
    snapshot: whether to take a blender snapshot or not.
    tasks: a queue with taks--None if you wish this function to build the queue. Useful if you want to build a custom task queue for image conversion and masking. 
    This function will add tasks for model building.
    report_statistics: should this report the time taken for things to build at the end? Default True.
    canceltreadedevent: an event to signal to all threads launched here that the job has been cancelled. Sent from the UI and hooked up to the cancel button.
    """
    config = Configurator.getConfig()
    
    buildfromformat = config.getProperty("processing","Build_From_Format")
    buildfromdir=inputdir 
    if not tasks or tasks.empty():
        tq = Queue()
        convertfiles = []
        filestomask = []
        for fl in os.listdir(inputdir):
            f = Path(Path(inputdir,fl))
            if f.is_file():
                if f.suffix.lower() in config.getProperty("processing","Source_Type"):
                    convertfiles.append(f)
                if f.suffix == buildfromformat:
                    filestomask.append(f)   
                else:
                    buildfromdir = Path(basedir,str(buildfromformat[1:]))
                    filestomask.append(Path(buildfromdir,f"{f.stem}{buildfromformat}"))
                    
        tq= setupConversionTasks(tq,
                                convertfiles,
                                basedir,False)
        tq= setupMaskingTasks(tq,filestomask,basedir,mask_option)
    else:
        tq = tasks
    tq = setupModelTasks(tq,filestomask,jobname,buildfromdir,basedir,mask_option)
    tq = setupPostTasks(tq,jobname,basedir,snapshot)
    executeTaskQueue(tq,True,report_statistics, cancelthreadevent)           


    
def buildModelCommand(args):
    """The wrapper function that extracts arguments from the command line and runs the build model function with the correct params based on them.
    Parameters:
    -------------------
    args: An argument object form the command line containing the following attributes: jobname (name of the job), photos (directory with photos in it), and
    outputdir (directory in which the project will be built.)"""

    job = args.jobname
    photoinput = args.photos
    outputdir = args.outputdirectory
    maskoption = int(args.maskoption)
    buildModel(job,photoinput,outputdir, MaskingOptions(maskoption))
    


def watchAndProcess(args):
    """WatchAndProcess: This function is a hook called by the UI to start the observer that grabs and converts files and manifests that get placed in a particular folder.
    It gets called from the Watch tab of the UI when "Watch" is pressed.
    Parameters:
    --------------------------------------------------------------
      args--an object with an attribute "inputdir". 
    """
    startWatcher(args.inputdir,None)

if __name__=="__main__":
    parser = argparse.ArgumentParser(prog="photogrammetryScripts")
    subparsers = parser.add_subparsers(help="Sub-command help")

    photogrammetryparser = subparsers.add_parser("photogrammetry", help="scripts for turning photographs into 3d models")
    photogrammetryparser.add_argument("jobname", help="The name of the project")
    photogrammetryparser.add_argument("photos", help="Place where the photos in tiff or jpeg format are stored.")
    photogrammetryparser.add_argument("outputdirectory", help="Where the intermediary files for building the model and the ultimate model will be stored.")
    photogrammetryparser.add_argument("--maskoption", type = str, choices=["0","1","2","3"], help = "How do you want to build masks:0 = no masks,\
                                    1 = Photoshop droplet(context aware select), \
                                    2 = Grayscale Thresholding, \
                                    3 = AI Inference Engine", 
                                    default=0)

    photogrammetryparser.set_defaults(func=buildModelCommand)

    watcherparser = subparsers.add_parser("watch", help="Watch for incoming files in the directory configured in JSON and build a model out of them.")
    watcherparser.add_argument("--inputdir", help="Optional input directory to watch. The watcher will watch config:watcher:listen_directory by default.", default="")
    watcherparser.set_defaults(func=watchAndProcess)      

    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()

