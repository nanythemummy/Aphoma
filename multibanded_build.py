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
        for fbk, fbv in v.items():
            #key will be front or back.
            refs = chunks[referencefiles][fbk]["files"]
            fbv["references"]=[]
            for reference in refs:
                referenceimage = Path(reference)
                output = Path(referencepath,f"{k}_{fbk}_ref_{referenceimage.stem}{referenceimage.suffix}")
                if not output.exists():
                    convertToGrayscaleAdjustBrightness(referenceimage,output,gray,channel,False,brightness)
                fbv["references"].append(output)
    return chunks



def sortFilesIntoBandsByName(filepath)->dict:
    multibanded_types= Configurator.getConfig().getProperty("photogrammetry","multibanded")
    getGlobalLogger(__name__).info("Loading multibanded info from config. Now sorting files.")
    files = Path(filepath).glob("*")
    chunks = {}
    for k,v in multibanded_types.items():
       
        if not k in chunks.keys():
    
            chunks[k]={}
            chunks[k]["front"]={"regex":re.compile(r"\S+_Front"+re.escape(v["path"])+r"[0-9]*.jpg",re.IGNORECASE),
                                  "files":[]
                                  }
            chunks[k]["back"]={"regex":re.compile(r"\S+_Back"+re.escape(v["path"])+r"[0-9]*.jpg",re.IGNORECASE),
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
    while(succeeded):
        task = taskqueue.get()
        succeeded &= task.setup()
        if succeeded:
            succeeded &= task.execute()
            task.exit()
        if taskqueue.empty():
            getGlobalLogger(__name__).info("Finished the tasklist, ending.")
            break
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
                if len(item[fb]["references"]) == 0:
                    chunks[k].pop(fb)
                    continue
                tasks.put(MetashapeTask_AlignPhotos({"input":sourcedir,
                                                            "output":projectdir,
                                                            "maskoption":MaskingOptions.NOMASKS,
                                                            "maskpath":"masks",
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
        chunklist = [f"{projectname}_{fb}{band}" for band in chunks.keys() if fb in chunks[band].keys()]
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
            tasks.put(MetashapeTask_AlignChunks({"input":sourcedir,
                        "output":projectdir,
                        "projectname":projectname,
                        "chunkname":f"{projectname}_{fb}visvis",
                        "chunklist":[f"{projectname}_{fb}{band}" for band in chunks.keys()],
                        "alignType":util.AlignmentTypes.ALIGN_BY_MARKERS}))
            tasks.put(MetashapeTask_BuildModel({"input":sourcedir,
                                "output":projectdir,
                                "projectname":projectname,
                                "chunkname":f"{projectname}_{fb}{k}"}))
            tasks.put(MetashapeTask_ReorientSpecial({"input":sourcedir,
                                        "output":projectdir,
                                        "projectname":projectname,
                                        "chunkname":f"{projectname}_{fb}{k}"}))
            tasks.put(MetashapeTask_ChangeImagePathsPerChunk({"input":sourcedir,
                            "output":projectdir,
                            "projectname":projectname,
                            "chunkname":f"{projectname}_{fb}{k}",
                            "replace_these":chunks[k][fb]["references"],
                            "to_replace_with":chunks[k][fb]["files"]}))
           
    for i in ["front","back"]:
        doc = MetashapeFileSingleton.getMetashapeDoc(projectname,Path(projectdir))
        chunklist = []
        for otherchunk in doc.chunks:
            if otherchunk.label.startswith(f"{projectname}_{i}"):
                chunklist.append(otherchunk)
        
        tasks.put(MetashapeTask_ResizeBoundingBoxFromMarkers({"input":sourcedir,
                                                        "output":projectdir,
                                                        "projectname":projectname,
                                                        "chunkname":f"{projectname}_{i}visvis",
                                                        "dimensionmarkers":[7,15,7,8]}
                                                        ))         
        tasks.put(MetashapeTask_CopyBoundingBoxToChunks({ "input":sourcedir,
                                                            "output":projectdir,
                                                            "projectname":projectname,
                                                            "chunkname":f"{projectname}_{i}visvis",
                                                            "chunklist":chunklist}))
    for k, item in chunks.items():
        for i in ["front","back"]:
            # tasks.put(MetashapeTask_ResizeBoundingBoxFromMarkers({"input":sourcedir,
            #                                             "output":projectdir,
            #                                             "projectname":projectname,
            #                                             "chunkname":f"{projectname}_{i}{k}",
            #                                             "dimensionmarkers":[7,15,7,8]}))
            if  item.get(fb,None) is None:
                continue
            tasks.put(MetashapeTask_BuildOrthomosaic({"input":sourcedir,
                            "output":projectdir,
                            "projectname":projectname,
                            "chunkname":f"{projectname}_{i}{k}"}))

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
    projdir = args.projectdir
    sourcedir = args.sourcedir
    projectname = args.projectname
    Configurator.getConfig().setProperty("photogrammetry","palette","Multibanded")
    chunks = sortFilesIntoBandsByName(sourcedir)
    chunks = setupReferences(chunks, projdir)
    tasks = setupTasksPhaseOne(chunks, sourcedir,projectname,projdir)
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
