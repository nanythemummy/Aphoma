from pathlib import Path
from os import mkdir,listdir,sep
import Metashape
import shutil
from util.ErrorCodeConsts import *
from util.InstrumentationStatistics import *
from util.util import MaskingOptions
from util.util import AlignmentTypes
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
        self.doc = None
        self.chunkname = argdict["chunkname"]
        self.chunk = None
    def setup(self):
        success,code = super().setup()
        self.doc =MetashapeFileSingleton.getMetashapeDoc(self.projectname,self.output)
        for chunk in self.doc.chunks:
            if chunk.label == self.chunkname:
                self.chunk = chunk
                break
        if self.chunk is None:
            success = False
            code = ErrorCodes.NO_CHUNK
            getLogger(__name__).warning("Setup task failed to execute because there is no chunk %s",self.chunkname)
        return success,code
    def exit(self):
        success = super().exit()
        return success, ErrorCodes.NONE


class MetashapeTask_AlignPhotos(MetashapeTask):
    """Task for aligning photos using metashape/building a sparse cloud. The dictionary passed in on init must include keys:
    projectname:str name of the project
    input:str a directory of pictures to operate on.
    output:str a place to put the results--this is the parent folder of the picture folder, usually.
    maskoption:MaskingOptions - a member of the enum util.MaskingOptions
    chunkname:str label of the chunk to operate on.
    photos: an optional array of photo paths--all photos in the input directory will be used if this is not present.
    """
    def __init__(self,argdict:dict):
        super().__init__(argdict)
        self.chunkname = argdict["chunkname"]
        self.maskoption = argdict["maskoption"] if "maskoption" in argdict.keys() else MaskingOptions.NOMASKS
        self.chunk = None
        self.maskpath = argdict["maskpath"]
        self.photos = argdict["photos"] if "photos" in argdict.keys() else []

    def __repr__(self):
        return "Metashape Task: Align Photos"
    def setup(self):
        #in order for this task to succeed, there must be a chunk, and there must be photos.
        success,code = super().setup()
        print(self.maskpath)
        if success is False and code is ErrorCodes.NO_CHUNK:
            #the only way this fails is if there is no chunk.
            self.chunk = self.doc.addChunk()
            self.chunk.label=self.chunkname
            self.doc.save()      
            getLogger(__name__).info('Added chunk %s.',self.chunkname)
            success = True
            code = ErrorCodes.NONE
        if self.maskoption is not MaskingOptions.NOMASKS and not self.maskpath.exists():
            mkdir(self.maskpath)
        p = [i for i in self.photos if Path(i).is_file() and Path(i).suffix.upper()==".JPG"]
        if len(self.photos)==0 or len([i for i in self.photos if Path(i).is_file() and Path(i).suffix.upper()==".JPG"])==0:
            success = False
            code = ErrorCodes.INVALID_FILE
        
        if not self.input.exists():
            success = False
            code = ErrorCodes.INVALID_FILE
        return success, code
    
    def loadPhotos(self):
        if len(self.photos)>0:
            for i in self.photos:
                if Path(i).suffix.upper() ==".JPG":
                    self.chunk.addPhotos(str(Path(self.input,i)))
        else:
            subdirs = [p for p in self.input.iterdir() if p.is_dir()]
            if len(subdirs)==0:
                photos = [str(f) for f in self.input.iterdir() if f.is_file() and f.suffix.upper()==".JPG"]
                self.chunk.addPhotos(photos)
            else:
                #if the folder passed in as an image folder has subdirectories, 
                # it is assumed that this is now a multibanded system, and each subdirectory will be loaded as a different band.

                getLogger(__name__).warning("Setting up a multibanded system because there are subdirectories in the photo input folder.")
                subdirfolders = []
                for subdir in subdirs:
                    p = [str(f) for f in subdir.iterdir() if f.is_file() and f.suffix.upper()==".JPG"]
                    p.sort()
                    subdirfolders.append(p)
                images =[]
                filegroups = []
                for  z in zip(*subdirfolders):
                    filegroups.append(len(z))
                    images+=z
                
                self.chunk.addPhotos(images,filegroups, Metashape.ImageLayout.MultiplaneLayout)          

    def loadMasks(self):
        maskpath = Path(self.output,self.maskpath)
        masks = listdir(maskpath)
        if len(masks)>0:
            getLogger(__name__).info("Loading masks from %s", maskpath)
            ext = Path(masks[0]).suffix #get the ext
            template = f"{maskpath}{sep}{{filename}}{ext}"
            self.chunk.generateMasks(template, Metashape.MaskingMode.MaskingModeFile)
        return
    def checkAlignment(self):
        unaligned = []
        cams = self.chunk.cameras
        for c in cams:
            if not c.transform:
                unaligned.append(c)
        return unaligned
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
       
        success, code = super().execute()
        if success:
            
            downscale_factor = Configurator.getConfig().getProperty("photogrammetry","sparse_cloud_quality")
            if len(self.chunk.cameras)==0:
                self.loadPhotos()
                if not self.maskoption is MaskingOptions.NOMASKS:
                    self.loadMasks()      
            if not self.chunk.point_cloud:   
                self.chunk.matchPhotos(downscale=downscale_factor,
                    generic_preselection=True,
                    reference_preselection=True,
                    reference_preselection_mode=Metashape.ReferencePreselectionMode.ReferencePreselectionSource,
                    filter_mask=(self.maskpath!=None and self.maskoption !=MaskingOptions.NOMASKS),
                    mask_tiepoints=False,
                    filter_stationary_points=True,
                    tiepoint_limit=0,
                    reset_matches=False)
                getLogger(__name__).info("Aligning Cameras.")
                self.chunk.alignCameras()
            try:
                    self.doc.save()
            except OSError as e:
                getLogger(__name__).error(e)
                success = False
                code = ErrorCodes.METASHAPE_FILE_LOCKED

        return success,code
    
    def exit(self):
        #verify that the build was a success.
        success,code = super().exit()
        if success:
            if not len(self.chunk.cameras) >0 and self.chunk.point_cloud and len(self.chunk.tie_points)>0:
                getLogger(__name__).error("Failed to create points or import cameras on chunk %s",self.chunk.label)
                success= False
                code = ErrorCodes.NO_TIEPOINTS
                return success, code
            unaligned = self.checkAlignment()
            if len(unaligned)>0:
                success = False
                code = ErrorCodes.UNALIGNED_CAMERAS
                getLogger(__name__).error("failing execution due to unaligned cameras %s on chunk %s", self.chunk.label, unaligned)
                return success, code
        return success, code

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
        success,code = super().setup()
        if self.chunk and self.palette_name:
            palettedict = util.load_palettes()
            self.palette_info = palettedict[self.palette_name]
        return success,code

    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success,code = super().execute()
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
                code = ErrorCodes.UNKNOWN
                success = False
                raise e
        return success,code
    
    def exit(self):
        #verify that the build was a success.
        success,code = super().exit()
        if success:
            if self.palette_info and "scalebars" in self.palette_info.keys():
                if  len(self.chunk.scalebars)==0:
                    success = False
                    code = ErrorCodes.NO_SCALEBARS_FOUND
                    getLogger(__name__).warning("The expected targets for this palette were not found on the model.")
        return success,code          
    
class MetashapeTask_AlignChunks(MetashapeTask):
    """
    Task object for aligning chunks. Right now, it only supports aligning by marker at the moment. It requires a dict with the following keys in it on init.
    projectname:str name of the project
    input:str a directory of pictures to operate on.
    output:str a place to put the results--this is the parent folder of the picture folder, usually.
    chunkname:str label of the chunk to operate on.
    chunklist: a list of names of chunks to align
    alignType: an alignment type as defined in util.alignmentTypes
    """
    def __init__(self,argdict:dict):
        super().__init__(argdict)
        pal = Configurator.getConfig().getProperty("photogrammetry","palette")
        self.alignType = argdict["alignType"]
        self.palette_name = pal if pal!="none" else None
        self.chunkstoalign = argdict.get("chunklist",None)
        if  self.palette_name and self.alignType == AlignmentTypes.ALIGN_BY_MARKERS:
            palettedict= util.load_palettes()
            self.palette_info = palettedict[self.palette_name]

    def __repr__(self):
        return "Metashape Task: Align Chunks by Marker"
    
    def setup(self):
        #for this to succeed, if in marker based alignment, there must be a palette.
        success,code = super().setup()
        if success:
            if  self.palette_name and self.alignType == AlignmentTypes.ALIGN_BY_MARKERS:
                palettedict= util.load_palettes()
                self.palette_info = palettedict[self.palette_name]
            else:               
                getLogger(__name__).info("Setup for align chunks failed. Check that the right alignment type was passed and that the palette type was specified.")
                success =False
                code = ErrorCodes.UNSUPPORTED_ALIGNMENT_TYPE
        return success,code
    
    def buildChunklist(self):
        chunklist = []  
        names =  [] if self.chunkstoalign is None else self.chunkstoalign
        for chunk in self.doc.chunks:
            if len(names)==0 or chunk.label in names:
                chunklist.append(chunk.key)
        return chunklist

    @timed(Statistic_Event_Types.EVENT_ALIGN_CHUNKS)
    def execute(self):
        if self.alignType == AlignmentTypes.ALIGN_BY_MARKERS:
            chunkstoalign = self.buildChunklist()
            markerlist = [marker.key for marker in self.chunk.markers]
            self.doc.alignChunks(chunkstoalign,self.chunk,method=1,markers=markerlist)
            self.doc.save()
        return True, ErrorCodes.NONE
    
    def exit(self):
        success,code=super().exit()
        return success,code

    
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
        success,code = super().setup()
        if self.chunk and self.palette_name:
            palettedict = util.load_palettes()
            self.palette_info = palettedict[self.palette_name]
        return success, code

    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success,code = super().execute()
        if success:
            try:
                if self.palette_name:
                    getLogger(__name__).info("Finding markers as defined in %s.", self.palette_name)
                    if not self.chunk.markers:
                        ModelHelpers.detect_markers(self.chunk,self.palette_info["type"])
                        self.doc.save()
            except Exception as e:
                getLogger(__name__).error(e)
                code = ErrorCodes.UNKNOWN
                success = False
                raise e
        return success,code
    
    def exit(self):
        "verifies that markers were detected if they were specified."
        success, code =  super().exit()
        if success:
            if self.palette_info:
                if len(self.chunk.markers)==0:
                    success = False
                    code = ErrorCodes.NO_MARKERS_FOUND
         
        
        if not success:
            getLogger(__name__).warning("No markers found for chunk %s",(self.chunkname))
        return success,code          

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
        success,code = super().execute()
        if success:
            try:     
                if self.chunk.tie_points and not self.chunk.model:  
                    thresholds = Configurator.getConfig().getProperty("photogrammetry","error_thresholds")
                    ModelHelpers.refine_sparse_cloud(self.doc, self.chunk,thresholds)
            except Exception as e:
                getLogger(__name__).error(e)
                code = ErrorCodes.UNKNOWN
                success = False
                raise e
        return success,code


class MetashapeTask_BuildModel(MetashapeTask):
    """
    Task object for building a model from depthmaps. It will build the depthmaps and then the model. It requires:
        input:str a directory of pictures to operate on.
        output:str a place to put the results--this is the parent folder of the picture folder, usually.
        chunkname:str label of the chunk to operate on.
        For it to run successfully, it the chunk it is operating on must have tie points but no model.

    """
    def __repr__(self):
        return "Metashape Task: Build Model from Depth Maps"
    
    def setup(self):
        success,code = super().setup()
        if success:
            if not self.chunk.tie_points:
                success = False
                code = ErrorCodes.NO_TIEPOINTS
        return success,code

    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success, code = super().execute()
        if success:                  
            if not self.chunk.model:
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
            try:
                self.doc.save()
            except OSError as e:
                getLogger(__name__).error(e)
                success = False
                code = ErrorCodes.METASHAPE_FILE_LOCKED
        return success,code

    def exit(self):
        #verify that the build was a success.
        success, code = super().exit()
        if success:
            if not self.chunk.model:
                success = False
                code = ErrorCodes.NO_MODEL_FOUND
        return success, code

class MetashapeTask_BuildTextures(MetashapeTask):

    """
    Task object for building textures on a model. It requires:
        input:str a directory of pictures to operate on.
        output:str a place to put the results--this is the parent folder of the picture folder, usually.
        chunkname:str label of the chunk to operate on.
        This will not execute if there are textures already, and it requires a model to succeed.
        It requires the texture_size and Texture_count config values to be set.

    """

    def __repr__(self):
        return "Metashape Task: Build UV Maps and Textures"
    
    def setup(self):
        success, code = super().setup()
        if success:
            if not self.chunk.model:
                success = False
                code = ErrorCodes.NO_MODEL_FOUND
        return success, code
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success, code = super().execute()
        if success:     
            if not len(self.chunk.model.textures)>0:
                pages = Configurator.getConfig().getProperty("photogrammetry","texture_count")
                tsize = Configurator.getConfig().getProperty("photogrammetry","texture_size")
                getLogger(__name__).info("Building UV Map and Texture for chunk %s",self.chunk.label)
                self.chunk.buildUV(page_count=pages, texture_size=tsize)
                self.chunk.buildTexture(texture_size=tsize, ghosting_filter=True)
            try: 
                self.doc.save()
            except OSError as e:
                getLogger(__name__).error(e)
                success = False
                code = ErrorCodes.METASHAPE_FILE_LOCKED
        return success,code
    
    def exit(self):
        #verify that the build was a success.
        success,code = super().exit()
        if not self.chunk.model.textures:
            success = False
            code = ErrorCodes.NO_TEXTURES_FOUND
        return success,code 
    


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
        pal = argdict.get("palettename",None)
        if pal is None:
            pal = Configurator.getConfig().getProperty("photogrammetry","palette") 
        self.palette_name = pal if pal != "none" else None
        self.axes = None

    def __repr__(self):
        return "Metashape Task: Reorient Model"
    
    def setup(self):
        success,code = super().setup()
        if self.palette_name:
            palettedict = util.load_palettes()
            self.palette_info = palettedict[self.palette_name]
            self.axes = ModelHelpers.find_axes_from_markers(self.chunk,self.palette_info)
        if len(self.axes)==0:
            code = ErrorCodes.NO_AXES
        return success, code
        
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success, code = super().execute()
        if success:
            if self.chunk.model:
                if len(self.axes)==0:
                    getLogger(__name__).warning("No axes on which to orient chunk %s",self.chunkname)
                else:
                    getLogger(__name__).info("Reorienting chunk %s according to markers on palette.",self.chunkname)
                    ModelHelpers.align_markers_to_axes(self.chunk,self.axes)
                    ModelHelpers.move_model_to_world_origin(self.chunk)
        return success,code
  
class MetashapeTask_ExportModel(MetashapeTask):
    """
    Task object for adding scales to an existing metashape doc. It requires a dict with the following keys on init.           
    projectname:str name of the project
    input:str a directory of pictures to operate on.
    output:str a place to put the results--this is the parent folder of the picture folder, usually.
    chunkname:str label of the chunk to operate on.
    extension: an extension or filetype to export to. Passed as a string with the dot, like ".obj"
    conform_to_shape: a boolean determining whether the model should be clipped to a particular boundary.

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
        success, code = super().setup()
        outputfolder = Configurator.getConfig().getProperty("photogrammetry","output_path")
        self.outputfolder = Path(self.output,outputfolder)
        self.outputfile = util.get_export_filename(self.chunkname.replace(" ",""),self.extn)
        return success, code
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success, code = super().execute()
        if success:
            getLogger(__name__).info("Now, exporting chunk %s as %s",self.chunk.label,self.outputfile )
            self.chunk.exportModel(path=str(Path(self.outputfolder,f"{self.outputfile}{self.extn}")),
                                texture_format = Metashape.ImageFormat.ImageFormatPNG,
                                embed_texture=(self.extn==".ply"),
                                clip_to_boundary=self.conform_to_shape )
        return success, code
    
    def exit(self):
        success, code = super().exit()
        if not Path(self.outputfile,self.outputfolder).exists():
            success = False
            code = ErrorCodes.EXPORT_FAILURE_MODEL
        return success, code  
    
class MetashapeTask_ExportOrthomosaic(MetashapeTask):

    def __repr__(self):
        return "Metashape Task: Export Orthomosaic"
    def setup(self):
        success, code = super().setup()
        if success:
            outputfolder = Configurator.getConfig().getProperty("photogrammetry","output_path")
            self.outputfolder = Path(self.output,outputfolder)
            if not self.chunk.orthomosaic:
                getLogger(__name__).warning("Failing the orthomosaic export because there's no orthomosaic for chunk %s",self.chunkname)
                success = False
                code = ErrorCodes.NO_ORTHOMOSAIC
        return success,code

            
    def execute(self):
        success, code = super().execute()
        if success:
            resolutionx = float(Configurator.getConfig().getProperty("photogrammetry","orthomosaic_mtopixel_x"))
            resolutiony = float(Configurator.getConfig().getProperty("photogrammetry","orthomosaic_mtopixel_y"))
            self.chunk.exportRaster(str(Path(self.output,self.outputfolder,f"{self.chunkname}_Orthomosaic.tif")),
                                    format = Metashape.RasterFormat.RasterFormatTiles,
                                    image_format=Metashape.ImageFormat.ImageFormatTIFF,
                                    raster_transform = Metashape.RasterTransformType.RasterTransformNone,
                                    resolution_x=resolutionx,
                                    resolution_y = resolutiony)
        return success, code
    
    def exit(self):
        success, code  = super().exit()
        expectedoutput = Path(self.output,self.outputfolder,f"{self.chunkname}_Orthomosaic.tif")
        if not expectedoutput.exists():
            getLogger(__name__).warning("Export Orthomosaic did not succeed because File %s was not created.",expectedoutput)
            success =False
            code = ErrorCodes.EXPORT_FAILURE_ORTHOMOSAIC
        return success, code
    

class MetashapeTask_BuildOrthomosaic(MetashapeTask):
    """
    Task object for building an orthomosaic. It will build the orthomosaic for the chunk.
    It requires:
        input: str - a directory of pictures to operate on.
        output: str - a place to put the results (parent folder of the picture folder, usually).
        chunkname: str - label of the chunk to operate on.
    For it to run successfully, the chunk must have a model and no orthomosaic.
    """
    def __init__(self, argdict: dict):
        super().__init__(argdict)

    def __repr__(self):
        return "Metashape Task: Build Orthomosaic"
    
    def setup(self):
        success,code = super().setup()
        if not self.chunk.model:
            success = False
            code = ErrorCodes.NO_MODEL_FOUND
        return success,code
    
    @timed(Statistic_Event_Types.EVENT_BUILD_ORTHOMOSAIC)
    def execute(self):
        success, code = super().execute()
        if success: 
            # Only build orthomosaic if there is a model and no orthomosaic yet
            if self.chunk.model and not self.chunk.orthomosaic:
                getLogger(__name__).info("Building Orthomosaic.")
                scalex = Configurator.getConfig().getProperty("photogrammetry","orthomosaic_mtopixel_x")
                scaley = Configurator.getConfig().getProperty("photogrammetry","orthomosaic_mtopixel_y")
                self.chunk.buildOrthomosaic(
                    surface_data=Metashape.DataSource.ModelData,
                    blending_mode=Metashape.BlendingMode.MosaicBlending,
                    resolution_x=scalex,
                    resolution_y=scaley
                )
            try:
                self.doc.save()
            except OSError as e:
                getLogger(__name__).error(e)
                success = False
                code = ErrorCodes.METASHAPE_FILE_LOCKED
        return success, code

    def exit(self):
        # Verify that the orthomosaic was built successfully
        success, code = super().exit()
        if not hasattr(self.chunk, 'orthomosaic'):
            success = False
            code = ErrorCodes.NO_ORTHOMOSAIC
        return success, code