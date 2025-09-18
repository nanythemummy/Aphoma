
from pathlib import Path, PurePosixPath
from os import mkdir
import shutil
import re
import Metashape
import cv2
from util.InstrumentationStatistics import *
from util.util import MaskingOptions
from util.util import AlignmentTypes
from util.PipelineLogging import getLogger as getGlobalLogger
from util.Configurator import Configurator
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from util import util
from photogrammetry import ModelHelpers
from tasks.MetashapeTasks import MetashapeTask, MetashapeTask_DetectMarkers

# This file contains metashape tasks that are unusual, one-off, or special. Tasks in it can be experimental.
# They do things that are outside of the normal model building workflow. Eventually, if tasks from here improve on the general
# functionality of the original, they may be ported over to the main metashape tasks file.



def checkMarkerLabelExists(chunk, labelname):
    for m in chunk.markers:
        if m.label ==labelname:
            return m
    return None
def copyMarkersFromChunkToOtherChunk(chunk1,chunk2):
    #The parameters are chunk1: The chunk you are copying the markers from, and chunk2: the chunk you are copying the markers to.
    print(f"copying markers from {chunk1.label} to {chunk2.label}")
    pat = re.compile(r"\S+?([0-9]+)$")
    photostomarkers={}
    if len(chunk1.markers)>0:
        for m in chunk1.markers:
            for camera in chunk1.cameras:
                if camera in m.projections.keys():
                    projection = m.projections[camera]
                    x = projection.coord.x
                    y = projection.coord.y
                    mat = pat.match(Path(camera.photo.path).stem)
                    if mat is not None:
                        photonumber = mat.group(1)
                        if  photonumber not in photostomarkers.keys():
                            photostomarkers[photonumber] = []
                        photostomarkers[photonumber].append({"name":m.label,"x":x,"y":y })
        print(photostomarkers)
        for cam in chunk2.cameras:
            camname=Path(cam.photo.path).stem
            mat = pat.match(camname)
            if mat is not None:
                camnum = mat.group(1)
                if camnum in photostomarkers.keys():
                    newmarkers = photostomarkers[camnum]
                    for marker in newmarkers:
                        mk = checkMarkerLabelExists(chunk2,marker["name"]) or chunk2.addMarker()
                        mk.label= marker["name"]
                        mk.projections[cam]=Metashape.Marker.Projection(Metashape.Vector([marker["x"],marker["y"]]),True)

class MetashapeTask_ReorientSpecial(MetashapeTask):

    """
    Task object for reorienting a model in space based on a pre-defined x and y axis where points on an x-y plane are arbitrarily specified at runtime. It requires:
        input:str a directory of pictures to operate on.
        output:str a place to put the results--this is the parent folder of the picture folder, usually.
        chunkname:str label of the chunk to operate on.

        It assumes that if you are working from a palette of computer readable markers, the name of this palette is already defined in config.json or via
        the UI. NOTE: THIS OPERATION DOES NOT SAVE.

    """
    def __init__(self,argdict:dict):
        print(f"initializing {__name__}")
        super().__init__(argdict)
        self.palette_info = None 
        pal = Configurator.getConfig().getProperty("photogrammetry","palette") 
        self.palette_name = pal if pal != "none" else None
        self.axes=None

    def __repr__(self):
        return "Metashape Task: Reorient Model--SPECIAL"
    
    def setup(self):
        success = super().setup()
        
        if self.chunk and self.palette_name:
            print("Calculating axes.")
            palettedict = util.load_palettes()
            self.palette_info = palettedict[self.palette_name]
            self.axes, planedata, xaxisdata = ModelHelpers.find_axes_from_markers_in_plane(self.chunk,self.palette_info)
            if self.axes and planedata and xaxisdata:
                getGlobalLogger(__name__).info("Found axis from markers: axes: %s.",self.axes)
                getGlobalLogger(__name__).info("Found planes: %s to %s to %s : (%s,%s,%s)", planedata[0]['name'],planedata[1]['name'],planedata[2]['name'],planedata[0]['pos'],planedata[1]['pos'],planedata[2]['pos'])
                getGlobalLogger(__name__).info("Found x-axis: %s to %s : (%s,%s)",xaxisdata[0]['name'],xaxisdata[1]['name'],xaxisdata[0]['pos'],xaxisdata[1]['pos'])
            else:
                success = False
        return success
        
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success = super().execute()
        if success:
            try:     
                if self.chunk.model:
                    if len(self.axes)==0:
                        getGlobalLogger(__name__).warning("No axes on which to orient chunk %s",self.chunkname)
                    else:
                        getGlobalLogger(__name__).info("Reorienting chunk %s according to markers on palette.",self.chunkname)
                        ModelHelpers.align_markers_to_axes(self.chunk,self.axes,1.0)
                        ModelHelpers.move_model_to_world_origin(self.chunk)
            except Exception as e:
                getGlobalLogger(__name__).error(e)
                success = False
                raise e
        return success
class MetashapeTask_CopyMarkersFromChunk(MetashapeTask):
    """
    Task object for copying a set of markers from one set of identical images to another. Use for when you have a camera with two sensors taking two imagesets where one imageset doesn't record the black and white
    color data of the targets.
    -This expects an argdict on init with: {"otherchunk":The name of the chunk you want to copy the markers from.
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
       super().__init__(argdict)
       self.otherchunkname = argdict["otherchunk"]
       self.otherchunk=None
 
    def __repr__(self):
        return "Metashape Task: Copy markers from a specified second chunk"
    
    def setup(self):
        success = super().setup()
        if success and self.chunk:
            doc = self.doc
            for c in doc.chunks:
                getGlobalLogger(__name__).info("current chunk is: %s Looking for chunk %s",c.label,self.otherchunkname)
                if c.label == self.otherchunkname:
                    self.otherchunk = c
                    break
            success = success and (self.otherchunk is not None)
        return success
    
    def execute(self):
        print("copying markers")
        copyMarkersFromChunkToOtherChunk(self.otherchunk,self.chunk)
        return len(self.otherchunk.markers)==len(self.chunk.markers)
class MetashapeTask_ResizeBoundingBox(MetashapeTask):
    """
    Task object for copying a set of markers from one set of identical images to another. Use for when you have a camera with two sensors taking two imagesets where one imageset doesn't record the black and white
    color data of the targets.
    -This expects an argdict on init with: {"width_depth_height":list with float members detailing the dimensions of the box in meters.
                                            "centerpoint": list with x,y,z of the box centerpoint
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
       super().__init__(argdict)
       self.width_depth_height = argdict["width_depth_height"]
       self.centerpoint = argdict["centerpoint"]
 
    def __repr__(self):
        return "Metashape Task: SetBoundingBoxDimensions"
    
    def setup(self):
        success = super().setup()
        return success
    
    def execute(self):
        
        getGlobalLogger(__name__).info("At least I got here.")
        #transform local coordinates to the coordinate reference system if there is one.
        region = self.chunk.region
        region.size =Metashape.Vector(self.width_depth_height)
        region.center = Metashape.Vector(self.centerpoint)
        self.chunk.region = region
        #set the bounding box rotation to be the same as the object.

class MetashapeTask_ImportModel(MetashapeTask):
    """
    This is a task for importing a saved out model as the model of an object, with the expectation that you want to project pictures onto it.
    -This expects an argdict on init with: {"modelfilename": full path of the model to load.
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
        super().__init__(argdict)
        self.modelfilename = Path(argdict["modelfilename"])
      
    def __repr__(self):
        return "Metashape Task: ImportModel"
   
    def setup(self):
        success = super().setup()
        success = success and self.modelfilename.is_file()
        return success
   
    def execute(self):
        getGlobalLogger(__name__).info("At least I got here.")
        #transform local coordinates to the coordinate reference system if there is one.
        self.chunk.importModel(str(self.modelfilename),
                               Metashape.ModelFormat.ModelFormatPLY if self.modelfilename.suffix.upper()==".PLY" else Metashape.ModelFormat.ModelFormatOBJ,
                                replace_asset = True)
        if not self.chunk.model:
            return False
        else:
            return  True

        #set the bounding box rotation to be the same as the object.


class MetashapeTask_ChangeImagePathsPerChunk(MetashapeTask):
    """
    Task object for copying a set of markers from one set of identical images to another. Use for when you have a camera with two sensors taking two imagesets where one imageset doesn't record the black and white
    color data of the targets.
    -This expects an argdict on init with: {"replace_these: a list of images to replace
                                            "to_replace_with":a 1:1 list of image paths to replace the existing images with.
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
       super().__init__(argdict)
       self.replacenames = argdict["to_replace_with"]
       self.imagestoreplace = argdict["replace_these"]
    
    def __repr__(self):
        return "Metashape Task: Repalce images in chunk with others."
    
    
    def execute(self):
        for c in self.chunk.cameras:
            if c.type == Metashape.Camera.Type.Regular:
                for i,cams in enumerate(self.imagestoreplace):
                    temp = PurePosixPath(cams)
                    metashapepath = str(c.photo.path)
                    if str(temp)==metashapepath:
                        newpath = str(PurePosixPath(self.replacenames[i]))
                        photocopy = c.photo.copy()
                        photocopy.path  = str(PurePosixPath(newpath))
                        c.photo = photocopy
                        getGlobalLogger(__name__).info("replacing %s with %s",metashapepath,newpath)
                        break
        marker = self.chunk.addMarker() #this is a nasty hack because metashape doesn't save paths if that's all you do before you save.
        self.doc.save()
        self.chunk.remove(marker)

        self.doc.save()
        return True



class MetashapeTask_DetectMarkersFromThresholdedImage(MetashapeTask_DetectMarkers):
    """
    Task object for detecting markers from a thresholded image set. This takes an image set, thresholds them, detects markers,
    then copies the markers back onto the original images. Why would you ever want to do this? Well, say you have an image with UV light
    in purple and black that is too dark to detect white on black targets (which are blue on deeper blue anyway). This converts to black and white, 
    detects markers, then copies the markers back onto your blue and purple image.
    -This expects an argdict on init with: {"threshold":The intensity above which a grayscale pixel ought to be white rather than black.
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}

    """


    def __init__(self,argdict:dict):
        print(f"initializing {__name__}")
        super().__init__(argdict)
        self.oldchunk = self.chunk
        self.threshold = argdict["threshold"]
        self.deletetemp = True

    def __repr__(self):
        return "Metashape Task: Detect Markers from Thresholded Images"
    

    
    def setup(self):
        success = super().setup()
        if success and self.chunk:
            success = super().setup()
            doc = MetashapeFileSingleton.getMetashapeDoc(self.projectname,self.output)
            currentworkingdir = Path(doc.path).parent
            photostomunge=[]
            tempdir = Path(currentworkingdir,"temp")
            try:
                mkdir(tempdir)
            except FileExistsError:
                self.deletetemp = False
            for camera in self.chunk.cameras:
                impath = camera.photo.path
                cam = cv2.imread(impath)
                bw = cv2.cvtColor(cam,cv2.COLOR_BGR2GRAY)
                _,mask = cv2.threshold(bw,self.threshold,255,cv2.THRESH_BINARY)
                outdir =str(Path(tempdir,Path(impath).name))
                photostomunge.append(outdir)
                cv2.imwrite(str(outdir),mask)
            self.oldchunk = self.chunk
            self.chunk= doc.addChunk()
            self.chunkname = self.chunk.label = "Tempchunk"
            doc.chunk = self.chunk
            for photo in photostomunge:
                if Path(photo).suffix.upper() ==".JPG":
                    self.chunk.addPhotos(photo)
        return success
        
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success = super().execute()
        if success:
            copyMarkersFromChunkToOtherChunk(self.chunk,self.oldchunk)
        return success
    
    def exit(self):
        doc = MetashapeFileSingleton.getMetashapeDoc(self.projectname,self.output)
        if doc.chunk.label =="Tempchunk":
            tempchunk = doc.chunk
            doc.chunk = self.oldchunk
            self.chunk = doc.chunk
            self.chunkname = doc.chunk.label
            doc.remove(tempchunk)
            doc.save()
        if self.deletetemp:
            shutil.rmtree(Path(Path(doc.path).parent,'temp'))
        


    