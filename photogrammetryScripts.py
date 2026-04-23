


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
#logger is a logger. all methods to go to the console in the ui should use this so that we can filter the normal metashape and debugging messages from things like 
#instrumentation.
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
                        tq=setup_conversion_tasks(tq,[f],processedpath,False)     
                fullmanifest[destsubfolder].append(processedfile)
            if is_masked:
                maskfile =Path(maskpath,f"{f.stem}{maskext}")
                if not maskfile.exists():
                    get_logger().info("Warning: did not find mask for %s in %s. Attempting to make one.", f.name,maskpath)
                    masksource = Path(processedpath,"jpg",f"{f.stem}.jpg")
                    tq=setup_masking_tasks(tq,[masksource],processedpath,mode)
                fullmanifest["masks"].append(maskfile)
        else:
            get_logger().warning("Did not find Original file: %s in %s. Manifest verification will fail.",f.name,basedir)
            foundallfiles = False
    execute_task_queue(tq,True,False,cancelevent)
    return foundallfiles,fullmanifest, tq

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

        ext = os.path.splitext(event.src_path)[1]
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
            build_model_from_manifest(self._event_queue,eventpath,mode)
        else:
            e = Path(eventpath)
            eventpathext = Path(eventpath).suffix.lower()
            processedpath = Path(scratchdir,"processed")
            predictedfinal = Path(processedpath,buildtype[1:],f"{e.stem}{buildtype}")
            filedest = Path(processedpath,eventpath.suffix[1:])
            if eventpathext.lower() not in desttype or len(desttype)>0: 
                #basically run this if there are multiple conversion types and the input is one of them or if the input is not in the list of output types.
                setup_conversion_tasks(self._event_queue,[e],processedpath, False)
                if eventpathext.lower() in desttype:
                    copy_file_to_dest([eventpath],filedest, False)
                
            else:
                copy_file_to_dest([eventpath],filedest, False)
            
            if mode !=  MaskingOptions.NOMASKS.value:
               setup_masking_tasks(self._event_queue,[predictedfinal],processedpath,mode)
                    
            execute_task_queue(self._event_queue,True,False,self.cancel_event)

   
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
                while True:
                    time.sleep(3)
                    last_size = current_size
                    current_size = newpath.stat().st_size
                    print(f"{last_size} :{current_size} for {newpath}")
                    if current_size==last_size:
                        break
                if current_size != 0:
                    self.process_incomming_file(newpath)



def startWatcher(watchdir:Path, cancelevent:threading.Event = None):
    
    eq = Queue()
    fshandler = FSWatcherHandler(eq, cancelevent)
    fsobserver = Observer()
    fsobserver.schedule(fshandler,watchdir,recursive=True)
   
    fsobserver.start()
    while not cancelevent.is_set():
        time.sleep(3)
    fsobserver.stop()
    fsobserver.join()


class Watcher:
    """These classes are part of a filesystem watcher which watches for the 
    appearance of a manifest file in the desired directory, then builds a model with the pictures
    
    Methods:
    ------------------------
    __init__(self,directory):initializes the class to watch a particular directory, configurabe in config.json.
    run(): makes a watcherHandler object and waits for it to intercept filesystem events.
    """
    def __init__(self,  watchdir:str, isSender = False, projectname=""):
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

        global MANIFEST
        MANIFEST = Manifest(self.projectname)
        handler = WatcherSenderHandler()

        self.observer.schedule(handler,self.watched_dir,recursive=True)
        self.observer.start()
        try:
            get_logger().info("Waiting for pictures to process.")
            listening=True
            print("Type F to Finish.")           
            while listening :
                time.sleep(1)
                if self.stoprequest:
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
def build_snapshot(projname,basefolder):
    cfg=Configurator.getConfig()
    fn  = get_export_filename(projname,"obj")
    objpath = Path(basefolder,"output",f"{fn}.obj")
    if objpath.exists():
        MeshlabHelpers.snapshot(objpath,
                                cfg.getProperty("postprocessing","rot_x"),
                                cfg.getProperty("postprocessing","rot_y"),
                                cfg.getProperty("postprocessing","rot_z"),True)

#This script contains the full automation flow and is triggered by the watcher
def build_model_from_manifest(tq:Queue,manifestfile:str, maskmode:MaskingOptions):
    """Builds a model from the files listed in a text file manifest.

    Parameters:
    -----------
    manifest: A path to a text file manifest with a comma seperated list of paths to image files.
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
        build_model(projname,Path(project_folder,bformat),project_folder,maskmode,snapshot=True,tasks=tq)

def execute_task_queue(taskqueue:Queue,stop_on_empty=True, report_statistics=True, cancelthreadevent:threading.Event = None):
    getGlobalLogger(__name__).info("Executing Tasklist.")
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
                getGlobalLogger(__name__).error("Phase %s for Task %s failed with error %s",phase, str(task),ErrorCodes.numToFriendlyString(code))
                FINISHED=True
                break
        
        if stop_on_empty and taskqueue.empty() or (cancelthreadevent and cancelthreadevent.is_set()):
            FINISHED = True
            getGlobalLogger(__name__).info("Finished the tasklist, ending.")
        
    if report_statistics:
        statistics.getStatistics().logReport()
        statistics.destroyStatistics()
        MetashapeFileHandleSingleton.MetashapeFileSingleton.destroyDoc() #gets created by metashape tasks "align photos."


def setup_conversion_tasks(task_queue:Queue,filestoconvert:list,basedir:Path,profile_correction:"False")->Queue:
    config = Configurator.getConfig()
    conversiontypes = config.getProperty("processing","Destination_Type")
    sourcetypes = config.getProperty("processing","Source_Type")
    desttype = config.getProperty("processing","Build_From_Format")

    if desttype not in conversiontypes:
       getGlobalLogger(__name__).error(" %s is not in list of conversion formats. Defaulting to JPG.",desttype)
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

def setup_masking_tasks(task_queue:Queue, pathlist:list, basedir:Path, mask_option=MaskingOptions.NOMASKS)->Queue:
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

def setup_post_tasks(task_queue:Queue,jobname:str,basedir:Path)->Queue:
    config = Configurator.getConfig()
    outputpath = Path(basedir,config.getProperty("photogrammetry","output_path"))
    objname =  Path(outputpath,get_export_filename(jobname,config.getProperty("photogrammetry","export_as")))
    objfullname = f"{objname}{config.getProperty("photogrammetry","export_as")}"

    if config.getProperty("postprocessing","script_directory") != "" and \
    config.getProperty("postprocessing","blender_exec")!="":
        task_queue.put(BlenderTasks.BlenderSnapshotTask({"inputobj":objfullname,"output":outputpath,"scale":True}))
    return task_queue

def setup_model_tasks(task_queue:Queue,pathlist:list,jobname:str,inputdir:Path,basedir:Path,mask_option=MaskingOptions.NOMASKS):
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

def build_model(jobname,
                inputdir,
                basedir,
                mask_option=MaskingOptions.NOMASKS,
                snapshot=False,
                tasks:Queue=None, 
                report_statistics=True,
                cancelthreadevent:threading.Event = None):
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
    tq = Queue() if not  tasks else tasks
    buildfromformat = config.getProperty("processing","Build_From_Format")
    buildfromdir= Path(basedir,str(buildfromformat[1:]))
    convertfiles = []
    for fl in os.listdir(inputdir):
        f = Path(fl)
        if f.suffix in config.getProperty("processing","Source_Type"):
            convertfiles.append(f)
    tq= setup_conversion_tasks(tq,
                              convertfiles,
                              basedir,False)
    filestouse = []
    for images in os.listdir(inputdir):
        filestouse.append(Path(buildfromdir,f"{Path(images).stem}{buildfromformat}"))
    tq= setup_masking_tasks(tq,filestouse,basedir,mask_option)
    tq = setup_model_tasks(tq,filestouse,jobname,buildfromdir,basedir,mask_option)
    tq = setup_post_tasks(tq,jobname,basedir)
    execute_task_queue(tq,True,report_statistics, cancelthreadevent)           

        # if snapshot:
        #     build_snapshot(jobname,basedir)

    
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
    




def split_shapes_cmd(args):

    """Wrapper script for taking a psx file and splitting the model inside into multiple cubic components which are exported as named obj files."""
    print("Got there.")
    inputdir = Path(args.inputdir)
    project = args.projectname
    projdir = Path(inputdir,f"{project}.psx")
    shapes = args.shapenames.split(",")
    print(f"{projdir}")
    if projdir.exists():

        try:
            from photogrammetry import MetashapeTools
            MetashapeTools.splitModelIntoShapes(projdir)
        except ImportError as e:
            print(f"{e.msg}: You should try downloading the metashape python module from Agisoft and installing it. See Readme for more details.")
            raise e




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
    inputdir = Path(args.imagedirectory)
    outputdir = Path(args.outputdirectory)
    tq = Queue()

    if not os.path.exists(outputdir):
        os.makedirs(outputdir)
    convertfiles =   [f for f in os.listdir(inputdir) if Path(f).suffix in Configurator.getConfig().getProperty("processing","source_type")],

    tq = setup_conversion_tasks(tq,convertfiles,inputdir.parent,bool(args.profile_correction))
    execute_task_queue(tq,True,True, None)



def watch_and_process_cmd(args):
    startWatcher(args.inputdir,None)

if __name__=="__main__":
    parser = argparse.ArgumentParser(prog="photogrammetryScripts")
    subparsers = parser.add_subparsers(help="Sub-command help")
    convertprocessor = subparsers.add_parser("convert", help=" Convert a Raw file to another format ")
    convertprocessor.add_argument("imagedirectory", help="Directory of raw files to operate on.", type=str)
    convertprocessor.add_argument("outputdirectory", help="Directory to put the output processed files.", type=str)
    convertprocessor.add_argument("--profile_correction", action="store_true",help="Use Profile Correction?")
    convertprocessor.set_defaults(func=convert_raw_to_format_cmd)


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

   
    modelbyshapeparser = subparsers.add_parser("splitshapes", help="Splits a finished model into cube-shaped sub-components based on shapes pre-drawn by the user in metashape.")
    modelbyshapeparser.add_argument("inputdir",help="Directory of project")
    modelbyshapeparser.add_argument("projectname", type=str, help="Name of the psx file.")
    modelbyshapeparser.add_argument("shapenames", type=str, help="Comma-separated list of names for the individual shapes.")
    modelbyshapeparser.set_defaults(func = split_shapes_cmd)

    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()

