from pathlib import Path
from os import mkdir,listdir,sep
import Metashape
from util.InstrumentationStatistics import *
from util.util import MaskingOptions
from util.PipelineLogging import getLogger
from util.Configurator import Configurator
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from util import util
from photogrammetry import ModelHelpers

from tasks.BaseTask import BaseTask

class MetashapeTask(BaseTask):
    def __init__(self, argdict:dict):
        super().__init__()
        self.projectname = argdict["projectname"]
        self.input = Path(argdict["input"])
        self.output = Path(argdict["output"])
        self.doc =MetashapeFileSingleton.getMetashapeDoc(self.projectname,self.output)
        self.chunkname = argdict["chunkname"]
        self.chunk = None
    def setup(self):
        success = super().setup()
        for chunk in self.doc.chunks:
            if chunk.label == self.chunkname:
                self.chunk = chunk
                break
        if self.chunk is None:
            success = False
        return success
    def exit(self):
        success = super().exit()
        return success
    
class MetashapeTask_AlignPhotos(MetashapeTask):
    """Task for aligning photos using metashape/building a sparse cloud. The dictionary passed in on init must include keys:
    projectname:str name of the project
    input:str a directory of pictures to operate on.
    output:str a place to put the results--this is the parent folder of the picture folder, usually.
    maskoption:MaskingOptions - a member of the enum util.MaskingOptions
    chunkname:str label of the chunk to operate on.
    """
    def __init__(self,argdict:dict):
        super().__init__(argdict)
        self.chunkname = argdict["chunkname"]
        self.maskoption = argdict["maskoption"] if "maskoption" in argdict.keys() and argdict["maskoption"]!=MaskingOptions.NOMASKS else None
        self.chunk = None
        self.maskpath = Path(Configurator.getConfig().getProperty("photogrammetry","mask_path"))

    def __repr__(self):
        return "Metashape Task: Align Photos"
    def setup(self):
        #in order for this task to succeed, there must be a chunk, and there must be photos.
        success = super().setup()
        
        if success is False:
            #the only way this fails is if there is no chunk.
            self.chunk = self.doc.addChunk()
            self.chunk.label=self.chunkname
            self.doc.save()      
            getLogger(__name__).info('Added chunk %s.',self.chunkname)
            success = True
        if self.maskoption is not None and not self.maskpath.exists():
            mkdir(self.maskpath)
        success &= self.input.exists()
        return success
    
    def loadPhotos(self):
        images = listdir(self.input)
        getLogger(__name__).info("Loading images from %s", self.input)
        for i in images:
            if Path(i).suffix.upper() ==".JPG":
                self.chunk.addPhotos(str(Path(self.input,i)))

    def loadMasks(self):
        maskpath = Path(self.output,self.maskpath)
        masks = listdir(maskpath)
        if len(masks)>0:
            getLogger(__name__).info("Loading masks from %s", maskpath)
            ext = Path(masks[0]).suffix #get the ext
            template = f"{maskpath}{sep}{{filename}}{ext}"
            self.chunk.generateMasks(template, Metashape.MaskingMode.MaskingModeFile)
        return
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success = super().execute()
        if success:
            try:
                downscale_factor = Configurator.getConfig().getProperty("photogrammetry","sparse_cloud_quality")
                if len(self.chunk.cameras)==0:
                    self.loadPhotos()
                    self.loadMasks()      
                if not self.chunk.point_cloud:   
                    self.chunk.matchPhotos(downscale=downscale_factor,
                        generic_preselection=True,
                        reference_preselection=True,
                        reference_preselection_mode=Metashape.ReferencePreselectionMode.ReferencePreselectionSource,
                        filter_mask=(self.maskpath!=None),
                        mask_tiepoints=False,
                        filter_stationary_points=True,
                        tiepoint_limit=0,
                        reset_matches=False)
                    getLogger(__name__).info("Aligning Cameras.")
                    self.chunk.alignCameras()
                    self.doc.save()
            except Exception as e:
                getLogger(__name__).error(e)
                success = False
                raise e
        return success
    
    def exit(self):
        #verify that the build was a success.
        success = True
        if not len(self.chunk.cameras) >0 and self.chunk.point_cloud and len(self.chunk.tie_points)>0:
            getLogger(__name__).error("Failed to create points or import cameras on chunk %s",self.chunk.label)
            success= False
        success &= super().exit()
        return success          

class MetashapeTask_AddScales(MetashapeTask):
    
    """
    Task object for adding scales to an existing metashape doc. It requires a dict with the following keys on init.           
    projectname:str name of the project
    input:str a directory of pictures to operate on.
    output:str a place to put the results--this is the parent folder of the picture folder, usually.
    chunkname:str label of the chunk to operate on.

    It assumes that if you are working from a palette of computer readable markers, the name of this palette is already defined in config.json or via
    the UI.
    """
    def __init__(self,argdict:dict):
        super().__init__(argdict)
        self.palette_info = None 
        pal = Configurator.getConfig().getProperty("photogrammetry","palette") 
        self.palette_name = pal if pal != "none" else None

    def __repr__(self):
        return "Metashape Task: Add Scales"
    
    def setup(self):
        #in order for this task to succeed, there must be a chunk, and there must be photos.
        success = super().setup()
        if self.chunk and self.palette_name:
            palettedict = util.load_palettes()
            self.palette_info = palettedict[self.palette_name]
        return success

    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success = super().execute()
        if success:
            try:
                if len(self.chunk.markers) >0:
                    if "scalebars" in self.palette_info.keys() and not self.chunk.scalebars:
                        getLogger(__name__).info("Attempting to define scalebars.")
                        if self.palette_info["scalebars"]["type"] == "explicit":
                            ModelHelpers.build_scalebars_from_list(self.chunk,self.palette_info["scalebars"]["bars"])
                        elif self.palette_info["scalebars"]["type"]=="sequential":
                            ModelHelpers.build_scalebars_from_sequential_targets(self.chunk,self.palette_info["scalebars"])
                        self.doc.save() 
            except Exception as e:
                getLogger(__name__).error(e)
                success = False
                raise e
        return success
    
    def exit(self):
        #verify that the build was a success.
        success = True
        if self.palette_info:
            success &= len(self.chunk.markers)>0
        if "scalebars" in self.palette_info.keys():
            success &= len(self.chunk.scalebars)>0
        success &= super().exit()
        return success          
class MetashapeTask_DetectMarkers(MetashapeTask):
    """
    Task object for detecting computer readable targets in a metashape document. It requires a dict with the following keys on init.           
    projectname:str name of the project
    input:str a directory of pictures to operate on.
    output:str a place to put the results--this is the parent folder of the picture folder, usually.
    chunkname:str label of the chunk to operate on.

    It assumes that if you are working from a palette of computer readable markers, the name of this palette is already defined in config.json or via
    the UI. It requires that the palette variable be set in configuration.
    """
    def __init__(self,argdict:dict):
        super().__init__(argdict)
        self.palette_info = None 
        pal = Configurator.getConfig().getProperty("photogrammetry","palette") 
        self.palette_name = pal if pal != "none" else None

    def __repr__(self):
        return "Metashape Task: Detect Markers"
    
    def setup(self):
        #in order for this task to succeed, there must be a chunk, and there must be photos.
        success = super().setup()
        if self.chunk and self.palette_name:
            palettedict = util.load_palettes()
            self.palette_info = palettedict[self.palette_name]
        return success

    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success = super().execute()
        if success:
            try:
                if self.palette_name:
                    getLogger(__name__).info("Finding markers as defined in %s.", self.palette_name)
                    if not self.chunk.markers:
                        ModelHelpers.detect_markers(self.chunk,self.palette_info["type"])
                        self.doc.save()
            except Exception as e:
                getLogger(__name__).error(e)
                success = False
                raise e
        return success
    
    def exit(self):
        "verifies that markers were detected if they were specified."
        success = True
        if self.palette_info:
            success &= len(self.chunk.markers)>0
        success &= super().exit()
        return success          

class MetashapeTask_ErrorReduction(MetashapeTask):

    """
    Task object for reducing error on an existing sparse point cloud. It requires:
        input:str a directory of pictures to operate on.
        output:str a place to put the results--this is the parent folder of the picture folder, usually.
        chunkname:str label of the chunk to operate on.
        For it to run successfully, it the chunk it is operating on must have tie points but no model.

    """
    def __init__(self,argdict:dict):
        super().__init__(argdict)
        
    def __repr__(self):
        return "Metashape Task: Error Reduction Workflow"
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success = super().execute()
        if success:
            try:     
                if self.chunk.tie_points and not self.chunk.model:  
                    thresholds = Configurator.getConfig().getProperty("photogrammetry","error_thresholds")
                    ModelHelpers.refine_sparse_cloud(self.doc, self.chunk,thresholds)
            except Exception as e:
                getLogger(__name__).error(e)
                success = False
                raise e
        return success

    def exit(self):
        #verify that the build was a success.
        success = True
        success &= super().exit()
        return success            
    
class MetashapeTask_BuildModel(MetashapeTask):
    """
    Task object for building a model from depthmaps. It will build the depthmaps and then the model. It requires:
        input:str a directory of pictures to operate on.
        output:str a place to put the results--this is the parent folder of the picture folder, usually.
        chunkname:str label of the chunk to operate on.
        For it to run successfully, it the chunk it is operating on must have tie points but no model.

    """
    def __init__(self,argdict:dict):
        super().__init__(argdict)
        
    def __repr__(self):
        return "Metashape Task: Build Model from Depth Maps"

    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success = super().execute()
        if success:
            try:       
                if  self.chunk.tie_points and not self.chunk.model:
                    facecount = None or Configurator.getConfig().getProperty("photogrammetry","custom_face_count")
                    dmquality = Configurator.getConfig().getProperty("photogrammetry","model_quality")
                    targetfacecount = facecount or 200000
                    facecountconst = Metashape.FaceCount.CustomFaceCount if facecount else Metashape.FaceCount.HighFaceCount
                    getLogger(__name__).info("Building Depth Maps.")
                    self.chunk.buildDepthMaps(downscale=dmquality, filter_mode = Metashape.FilterMode.MildFiltering)
                    getLogger(__name__).info("Building Model.")
                    self.chunk.buildModel(source_data = Metashape.DataSource.DepthMapsData, 
                                            face_count = facecountconst,
                                            face_count_custom = targetfacecount)
                    getLogger(__name__).info("Cleaning up blobs on Model.")
                    ModelHelpers.cleanup_blobs(self.chunk)
                    getLogger(__name__).info("Closing Holes.")
                    ModelHelpers.close_holes(self.chunk)
                    self.doc.save()
            except Exception as e:
                getLogger(__name__).error(e)
                success = False
                raise e
        return success

    def exit(self):
        #verify that the build was a success.
        success = True
        if not self.chunk.model:
            success = False
        return (success & super().exit())          

class MetashapeTask_BuildTextures(MetashapeTask):

    """
    Task object for building textures on a model. It requires:
        input:str a directory of pictures to operate on.
        output:str a place to put the results--this is the parent folder of the picture folder, usually.
        chunkname:str label of the chunk to operate on.
        This will not execute if there are textures already, and it requires a model to succeed.
        It requires the texture_size and Texture_count config values to be set.

    """
    def __init__(self,argdict:dict):
        super().__init__(argdict)
        
    def __repr__(self):
        return "Metashape Task: Build UV Maps and Textures"
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success = super().execute()
        if success:
            try:     
                if not len(self.chunk.model.textures)>0:
                    pages = Configurator.getConfig().getProperty("photogrammetry","texture_count")
                    tsize = Configurator.getConfig().getProperty("photogrammetry","texture_size")
                    getLogger(__name__).info("Building UV Map and Texture for chunk %s",self.chunk.label)
                    self.chunk.buildUV(page_count=pages, texture_size=tsize)
                    self.chunk.buildTexture(texture_size=tsize, ghosting_filter=True)
                    self.doc.save()
            except Exception as e:
                getLogger(__name__).error(e)
                success = False
                raise e
        return success
    def exit(self):
        #verify that the build was a success.
        success = True
        if not self.chunk.model.textures:
            success = False
        return (success & super().exit())   
    
class MetashapeTask_Reorient(MetashapeTask):

    """
    Task object for reorienting a model in space based on a pre-defined x and y axis. It requires:
        input:str a directory of pictures to operate on.
        output:str a place to put the results--this is the parent folder of the picture folder, usually.
        chunkname:str label of the chunk to operate on.
        It assumes that if you are working from a palette of computer readable markers, the name of this palette is already defined in config.json or via
        the UI. NOTE: THIS OPERATION DOES NOT SAVE.

    """
    def __init__(self,argdict:dict):
        super().__init__(argdict)
        self.palette_info = None 
        pal = Configurator.getConfig().getProperty("photogrammetry","palette") 
        self.palette_name = pal if pal != "none" else None
        self.axes = None

    def __repr__(self):
        return "Metashape Task: Reorient Model"
    
    def setup(self):
        success = super().setup()
        if self.chunk and self.palette_name:
            palettedict = util.load_palettes()
            self.palette_info = palettedict[self.palette_name]
            self.axes = ModelHelpers.find_axes_from_markers(self.chunk,self.palette_info)
        return success
        
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success = super().execute()
        if success:
            try:     
                if self.chunk.model:
                    if len(self.axes)==0:
                        getLogger(__name__).warning("No axes on which to orient chunk %s",self.chunkname)
                    else:
                        getLogger(__name__).info("Reorienting chunk %s according to markers on palette.",self.chunkname)
                        ModelHelpers.align_markers_to_axes(self.chunk,self.axes)
                        ModelHelpers.move_model_to_world_origin(self.chunk)
            except Exception as e:
                getLogger(__name__).error(e)
                success = False
                raise e
        return success
  
class MetashapeTask_ExportModel(MetashapeTask):
    """
    Task object for adding scales to an existing metashape doc. It requires a dict with the following keys on init.           
    projectname:str name of the project
    input:str a directory of pictures to operate on.
    output:str a place to put the results--this is the parent folder of the picture folder, usually.
    chunkname:str label of the chunk to operate on.

    It assumes that if you are working from a palette of computer readable markers, the name of this palette is already defined in config.json or via
    the UI.
    """
    def __init__(self,argdict:dict):
        super().__init__(argdict)
        self.outputfolder = None
        self.outputfile = ""
        self.extn = argdict["extension"]
        self.conform_to_shape=argdict["conform_to_shape"]
    def __repr__(self):
        return "Metashape Task: Export Chunk"
    def setup(self):
        success = super().setup()
        outputfolder = Configurator.getConfig().getProperty("photogrammetry","output_path")
        self.outputfolder = Path(self.output,outputfolder)
        self.outputfile = util.get_export_filename(self.chunkname.replace(" ",""),self.extn)
        return success
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success = super().execute()
        if success:
            try:                
                getLogger(__name__).info("Now, exporting chunk %s as %s",self.chunk.label,self.outputfile )
                self.chunk.exportModel(path=str(Path(self.outputfolder,f"{self.outputfile}{self.extn}")),
                                    texture_format = Metashape.ImageFormat.ImageFormatPNG,
                                    embed_texture=(self.extn==".ply"),
                                    clip_to_boundary=self.conform_to_shape )
            except Exception as e:
                getLogger(__name__).error(e)
                success = False
                raise e
        return success
    
    def exit(self):
        success = True
        if not Path(self.outputfile,self.outputfolder).exists():
            success = False
        return (success & super().exit())          