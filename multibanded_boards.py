import argparse
import re
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
from queue import Queue
from util.Configurator import Configurator
from util.PipelineLogging import getLogger as getGlobalLogger
from util.util import * 
from util.InstrumentationStatistics import InstrumentationStatistics
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from processing.image_processing import convertToGrayscaleAdjustBrightness
from tasks.MetashapeTasks import *
from tasks.MetashapeTasksSpecial import *

def convertProxyImage(image:str,outputname:str,channels:int,brightness:float=1.0,gray:bool=False):
    #im not sure that the images that we want to generate a grayscale orthophoto have to be grayscale at this point, but let's give it a go 
    #based on JP's prior code.
    im = Image.open(image)

    imarr = np.array(im)
    imarr = cv2.cvtColor(imarr,cv2.COLOR_RGB2BGR)
    output_image = imarr
    if gray:
        output_image = np.zeros_like(imarr) 
        sourcechannel = imarr[:,:,ColorChannelConstants(channels).value]
        output_image[:,:,0]=sourcechannel
        output_image[:,:,1]=sourcechannel
        output_image[:,:,2]=sourcechannel

    output_image=cv2.multiply(output_image,brightness)
    #copy exif data to img_out
    out = Image.fromarray(cv2.cvtColor(output_image,cv2.COLOR_BGR2RGB))
    out.save(outputname,exif=im.getexif())

def convertOrthomosaicsToGray(projname,chunks,inputdirectory:Path):
    multibanded_types= Configurator.getConfig().getProperty("photogrammetry","multibanded")
    for k,v in chunks.items():
        c = multibanded_types[k].get("graychannel","b")
        chans={"r":util.ColorChannelConstants.NUMPY_RED,"g":util.ColorChannelConstants.NUMPY_GREEN,"b":util.ColorChannelConstants.NUMPY_BLUE}
        channel = chans.get(c,util.ColorChannelConstants.NUMPY_BLUE)
        gray = True if str(multibanded_types[k].get("grayscale_ortho","True")).upper() == "TRUE" else False
        brightness = float(multibanded_types[k].get("brightness",1.0))
        eightbit = True if str(multibanded_types[k].get("eightbit","True")).upper() == "TRUE" else False
        for fb, _ in v.items():
            orthopath = Path(inputdirectory,f"{projname}_{fb}{k}_Orthomosaic.tif")
            if orthopath.exists():
                convertToGrayscaleAdjustBrightness(orthopath,orthopath,gray,channel,eightbit,brightness)


def setupReferences(chunks:dict,basedir:Path)->dict:
    """
        Some bands of photos do not capture enough information to build a sparse cloud with. In this case, photos from another band will be 
        substituted in using the band specified in config.json at photogrammetry["multibanded"][bandtype]["pointcloud_reference"]
        The pictures from the other band are used to build the model and the pictures from the original band are substituted back in
        when it comes time to build the texture and orthomosaic.
        This is why pictures of the same number must have the same location in space.
        This function duplicates the files from that specified subs those files into another folder called reference within the base directory.
        The color data is discarded with the exception of the blue channel if desired, and the intensity of the channel is adjusted according
        to values specieid in the config.json. The path of the reference is then saved off in the datastructure which is returned from the function
        which is the same datastructure passed in with chunks with a new "references" key pointing to a list of reference photos for each band.
        

        Parameters:
        ----------------
        chunks: information on what files are getting subbed for what and what bands will be built. This is obtained from the sortFilesIntoBandsByName
        function. references will be tracked in this dictionary as well.
        basedir: the project base directory where products are saved.
        
        Returns:
        --------------
        A dictionary that is the same chunks dictionary as passed in where each band key has a new references key pointing to a list of paths containing the references 
        for each band. 
    """
    multibanded_types= Configurator.getConfig().getProperty("photogrammetry","multibanded")
    referencepath = Path(basedir,"references")
    if not referencepath.exists():
        os.mkdir(referencepath)
    for k,v in chunks.items():
        referencefiles = multibanded_types[k].get("pointcloud_reference",k)
        c = multibanded_types[k].get("graychannel","b")
        chans={"r":util.ColorChannelConstants.NUMPY_RED,"g":util.ColorChannelConstants.NUMPY_GREEN,"b":util.ColorChannelConstants.NUMPY_BLUE}
        channel = chans.get(c,util.ColorChannelConstants.NUMPY_BLUE)
        gray = True if str(multibanded_types[k].get("grayscale_ortho","True")).upper() == "TRUE" else False
        brightness = float(multibanded_types[k].get("brightness",1.0))
        for _, fbv in v.items():
            fbv["references"]=[]
            for im in fbv["files"]:
                expectedname = re.sub(re.escape(k), referencefiles, str(im), flags=re.IGNORECASE)
                expectedpath = Path(expectedname)
                if not expectedpath.exists():
                    getGlobalLogger(__name__).error("Reference channel images %s do not have identical numbers to current band %s",referencefiles,k)
                    return None
                else:
                    tempname = Path(referencepath,f"{im.stem}_ref_{expectedpath.stem}{expectedpath.suffix}")
                    if not tempname.exists():
                        convertToGrayscaleAdjustBrightness(expectedpath,tempname,gray,channel,False,brightness)
                    fbv["references"].append(tempname)

    return chunks



def sortFilesIntoBandsByName(filepath:Path)->dict:
    """
    Function sortFilesIntoBandsByName: Takes the files in a provided folder and stores them in a local datastructure based on 
    their filenames. This function breaks out whether this is the front or back of an object and the "bands" of the photo.
    The information for each band gets set in config.json.
    Parameters:
        filepath: The folder containing images to process. The images must be stored in this folder as this function is not recursive.
    Returns:
        A dictionary with the following format {irir:{front:[],back:[]},uvuv:{front:[],back:[] ...etc}}
        where the elements in the lists are filenames. This dictionary is used to track which pictures correspond to the others in different
        bands. Again, there is an assumption that photo 1 of each band will be in the same physical location.

    Additionally, this function uses the config values specified in config.json photogrammetry:multibanded. These can be finetuned to affect
    the resulting orthomosaics.
    """
    multibanded_types= Configurator.getConfig().getProperty("photogrammetry","multibanded")
    getGlobalLogger(__name__).info("Loading multibanded info from config. Now sorting files.")
    files = filepath.glob("*")
    chunks = {}
    for k,v in multibanded_types.items():
       
        if not k in chunks.keys():
    
            chunks[k]={}
            chunks[k]["front"]={"regex":re.compile(r"\S+_Front"+re.escape(v["path"])+r"_*[0-9]*.jpg",re.IGNORECASE),
                                  "files":[]
                                  }
            chunks[k]["back"]={"regex":re.compile(r"\S+_Back"+re.escape(v["path"])+r"_*[0-9]*.jpg",re.IGNORECASE),
                                "files":[]
                                }
    for file in files:
        for _, info in chunks.items():
            mf = info["front"]["regex"].match(file.name)
            mb = info["back"]["regex"].match(file.name)
            if mf:
                info["front"]["files"].append(file)
                break
            elif mb:
                info["back"]["files"].append(file)
                break
    getGlobalLogger(__name__).info("The following bands exist with the following number of pics, respectively. %s",
                                  [(a,b,len(chunks[a][b]["files"])) for a in chunks.keys() for b in chunks[a].keys() ] )
   
    return chunks

def executeTasklist(taskqueue:Queue):
    
    getGlobalLogger(__name__).info("Executing Tasklist.")
    succeeded = True
    finished = False
    phase = "setup"
    while(not finished):
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
            break
        if taskqueue.empty():
            finished = True
            getGlobalLogger(__name__).info("Finished the tasklist, ending.")
        

    InstrumentationStatistics.getStatistics().logReport()
    InstrumentationStatistics.destroyStatistics()
    MetashapeFileSingleton.destroyDoc() #gets created by metashape tasks "align photos."

def setupTasksPhaseOne(chunks:dict,sourcedir,projectname,projectdir):
    tasks = Queue()
    getGlobalLogger(__name__).info("Building Tasklist, including aligning, error reduction, and marker detection.")  
    for k,item in chunks.items():
            for fb in ["front","back"]:
                if  item.get(fb,None) is None:
                    continue
                if len(item[fb]["references"]) == 0 or len(item[fb]["files"]) == 0:
                    chunks[k].pop(fb)
                    continue
                tasks.put(MetashapeTask_AlignPhotos({"input":sourcedir,
                                                            "output":projectdir,
                                                            "usemasks":False,
                                                            "maskpath": Path(projectdir,"masks"),
                                                            "projectname":projectname,
                                                            "chunkname":f"{projectname}_{fb}{k}",
                                                            "photos":item[fb]["references"]
                                                            }))
                tasks.put(MetashapeTask_ErrorReduction({"input":sourcedir,
                                                            "output":projectdir,
                                                            "projectname":projectname,
                                                            "chunkname":f"{projectname}_{fb}{k}"

                }))
                tasks.put(MetashapeTask_DetectMarkers({"input":sourcedir,
                                "output":projectdir,
                                "projectname":projectname,
                                "chunkname":f"{projectname}_{fb}{k}"}))
                tasks.put(MetashapeTask_AddScales({"input":sourcedir,
                                        "output":projectdir,
                                        "projectname":projectname,
                                        "chunkname":f"{projectname}_{fb}{k}"}))

    
    for fb in ["front","back"]:  
        visvis = chunks.get("visvis",None)
        if visvis and fb in visvis.keys():

            chunklist = [f"{projectname}_{fb}{band}" for band in chunks.keys() if fb in chunks[band].keys() and band != "visvis"]
            tasks.put(MetashapeTask_AlignChunks({"input":sourcedir,
                            "output":projectdir,
                            "projectname":projectname,
                            "chunkname":f"{projectname}_{fb}visvis",
                            "chunklist":chunklist,
                            "alignType":util.AlignmentTypes.ALIGN_BY_MARKERS
        }
        ))
       
        
    tasks = setupTasksPhaseTwo(chunks,sourcedir,projectname,projectdir, tasks)  
    return tasks

def setupTasksPhaseTwo(chunks:dict,sourcedir,projectname,projectdir,tasklist = None):
    tasks = Queue() if tasklist is None else tasklist
    getGlobalLogger(__name__).info("Building Tasklist, including selective scales, orientation, alignment, model, and orthophoto")
    for k, item in chunks.items():
        for fb in ["front","back"]:
            if  item.get(fb,None) is None:
                continue

            tasks.put(MetashapeTask_BuildModel({"input":sourcedir,
                                "output":projectdir,
                                "projectname":projectname,
                                "chunkname":f"{projectname}_{fb}{k}"}))
    for fb in ["front","back"]:
        chunklist = [f"{projectname}_{fb}{band}" for band in chunks.keys() if fb in chunks[band].keys() and band != "visvis"]

        tasks.put(MetashapeTask_ReorientSpecial({"input":sourcedir,
                                    "output":projectdir,
                                    "projectname":projectname,
                                    "chunkname":f"{projectname}_{fb}visvis"}))
        tasks.put(MetashapeTask_AlignChunks({"input":sourcedir,
                                    "output":projectdir,
                                    "projectname":projectname,
                                    "chunkname":f"{projectname}_{fb}visvis",
                                    "chunklist":chunklist,
                                    "alignType":util.AlignmentTypes.ALIGN_BY_MARKERS}))
    for k, item in chunks.items():
        for fb in ["front","back"]:
            if  item.get(fb,None) is None:
                continue
                
            tasks.put(MetashapeTask_ChangeImagePathsPerChunk({"input":sourcedir,
                            "output":projectdir,
                            "projectname":projectname,
                            "chunkname":f"{projectname}_{fb}{k}",
                            "replace_these":chunks[k][fb]["references"],
                            "to_replace_with":chunks[k][fb]["files"]}))
           
    for i in ["front","back"]:
        #Build the visvis reference orthomosaic first so its projection/footprint can be reused below to
        #frame the other bands' orthomosaics to matching pixel dimensions.
        visvis = chunks.get("visvis",None)
        if visvis and i in visvis.keys():
            tasks.put(MetashapeTask_ResizeBoundingBoxFromMarkers({"input":sourcedir,
                                                "output":projectdir,
                                                "projectname":projectname,
                                                "chunkname":f"{projectname}_{i}visvis",
                                                "dimensionmarkers":[7,15,7,8]}
                                                ))    
            tasks.put(MetashapeTask_BuildOrthomosaic({"input":sourcedir,
                            "output":projectdir,
                            "projectname":projectname,
                            "chunkname":f"{projectname}_{i}visvis"}))

            tasks.put(MetashapeTask_ExportOrthomosaic({"input":sourcedir,
                            "output":projectdir,
                            "projectname":projectname,
                            "chunkname":f"{projectname}_{i}visvis"}))

        for k, item in chunks.items():
            if k == "visvis":
                continue
            if  item.get(i,None) is None:
                continue
            tasks.put(MetashapeTask_BuildOrthomosaic({"input":sourcedir,
                            "output":projectdir,
                            "projectname":projectname,
                            "chunkname":f"{projectname}_{i}{k}",
                            "referencechunk":f"{projectname}_{i}visvis"}))

            tasks.put(MetashapeTask_ExportOrthomosaic({"input":sourcedir,
                            "output":projectdir,
                            "projectname":projectname,
                            "chunkname":f"{projectname}_{i}{k}"}))
    for fb in ["front","back"]:
        tasks.put(MetashapeTask_BuildTextures({"input":sourcedir,
            "output":projectdir,
            "projectname":projectname,
            "chunkname":f"{projectname}_{fb}visvis"}))

        tasks.put(MetashapeTask_ExportModel({"input":sourcedir,
                "output":projectdir,
                "projectname":projectname,
                "chunkname":f"{projectname}_{fb}visvis",
                "extension":".ply",
                "conform_to_shape": False}))
            
    return tasks 

def build_multibanded_cmd(args):
    """
    Entry point for building aligned (hopefully) orthomosaics using picturesets of multibanded photos. You need to have a folder full of pictures of IR, UV, and/or visible light photos
    tken in the same physical locations. Each photo in the same location needs to have the same photo number and object number in this pattern, switching the photo type as necessary.
    {Objectname}_{Front OR Back}{IrIr, VisIr, VisVis, UvUv, UvVis}_{4-digit-photo number} 
    Params:
        args--an object containg the following attributes: 
        projectdir = the directory in which the products of the build will be stored.
        projectname = a name for the project.
        sourcedir = a folder full of specially named jpgs corresponding to photos of different bands.
    """
    projdir = args.projectdir
    sourcedir = args.sourcedir
    projectname = args.projectname
    Configurator.getConfig().setProperty("photogrammetry","palette","Multibanded")
    chunks = sortFilesIntoBandsByName(Path(sourcedir))
    chunks = setupReferences(chunks, Path(projdir))
    if chunks != None:
        tasks = setupTasksPhaseOne(chunks, Path(sourcedir),projectname,Path(projdir))
        executeTasklist(tasks)
        convertOrthomosaicsToGray(projectname,chunks,Path(projdir,"output"))
       
if __name__=="__main__":
    multibandparser = argparse.ArgumentParser()

    multibandparser.add_argument("sourcedir", help="Location of raw files")
    multibandparser.add_argument("projectdir",help="location to output files")   
    multibandparser.add_argument("projectname", help="The name of the project to build.")
    multibandparser.set_defaults(func=build_multibanded_cmd)
    args = multibandparser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        multibandparser.print_help()
