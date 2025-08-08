
from pathlib import Path
from os import mkdir
import shutil
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
            getGlobalLogger(__name__).info("Found axis from markers: axes: %s.",self.axes)
            getGlobalLogger(__name__).info("Found planes: %s to %s to %s : (%s,%s,%s)", planedata[0]['name'],planedata[1]['name'],planedata[2]['name'],planedata[0]['pos'],planedata[1]['pos'],planedata[2]['pos'])
            getGlobalLogger(__name__).info("Found x-axis: %s to %s : (%s,%s)",xaxisdata[0]['name'],xaxisdata[1]['name'],xaxisdata[0]['pos'],xaxisdata[1]['pos'])
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
    
class MetashapeTask_DetectMarkersFromThresholdedImage(MetashapeTask_DetectMarkers):
    """
    Task object for detecting markers from a thresholded image set. This takes an image set, thresholds them, detects markers,
    then copies the markers back onto the original images. Why would you ever want to do this? Well, say you have an image with UV light
    in purple and black that is too dark to detect white on black targets (which are blue on deeper blue anyway). This converts to black and white, 
    detects markers, then copies the markers back onto your blue and purple image.

    """


    def __init__(self,argdict:dict):
        print(f"initializing {__name__}")
        super().__init__(argdict)
        self.oldchunk = self.chunk
        self.threshold = argdict["threshold"]
        self.deletetemp = True

    def __repr__(self):
        return "Metashape Task: Detect Markers from Thresholded Images"
    
    def checkMarkerLabelExists(self,chunk, labelname):
        for m in chunk.markers:
            if m.label ==labelname:
                return m
        return None
    
    def setup(self):
        success = super().setup()
        if success and self.chunk:
            success = super().setup()
            doc = MetashapeFileSingleton.getMetashapeDoc(self.projectname,self.output)
            currentworkingdir = Path(doc.path).parent
            photostomunge=[]
            tempdir = Path(currentworkingdir,"temp")
            try:
                #getGlobalLogger(__name__).info("Making temp directory at %s",Path(Path(doc.path).parent,'temp'))
                
                print("Making temp directory at %s",Path(Path(doc.path).parent,'temp'))
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
            photostomarkers={}
            if len(self.chunk.markers)>0:
                for m in self.chunk.markers:
                    for camera in self.chunk.cameras:
                        if camera in m.projections.keys():
                            projection = m.projections[camera]
                            x = projection.coord.x
                            y = projection.coord.y
                            photoname = Path(camera.photo.path).stem
                            if  photoname not in photostomarkers.keys():
                                photostomarkers[photoname] = []
                            photostomarkers[photoname].append({"name":m.label,"x":x,"y":y })
        
            for cam in self.oldchunk.cameras:
                camname=Path(cam.photo.path).stem
                if camname in photostomarkers.keys():
                    newmarkers = photostomarkers[camname]
                    for marker in newmarkers:
                        mk = self.checkMarkerLabelExists(self.oldchunk,marker["name"]) or self.oldchunk.addMarker()
                        mk.label= marker["name"]
                        mk.projections[cam]=Metashape.Marker.Projection(Metashape.Vector([marker["x"],marker["y"]]),True)
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
        


    