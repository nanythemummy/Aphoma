
from pathlib import Path
from os import mkdir,listdir,sep
import Metashape
import shutil
from util.InstrumentationStatistics import *
from util.util import MaskingOptions
from util.util import AlignmentTypes
from util.PipelineLogging import getLogger
from util.Configurator import Configurator
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from util import util
from photogrammetry import ModelHelpers
from tasks.MetashapeTasks import MetashapeTask

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
        print(f"Chunkname is {self.chunkname}")
        success = super().setup()
        print(f"parent was setup")
        
        if self.chunk and self.palette_name:
            print("Calculating axes.")
            palettedict = util.load_palettes()
            
            self.palette_info = palettedict[self.palette_name]
            
            self.axes, planedata, xaxisdata = ModelHelpers.find_axes_from_markers_in_plane(self.chunk,self.palette_info)
            print(f"Found axis from markers: axes {self.axes},\n plane: {planedata[0]['name']} to {planedata[1]['name']} to {planedata[2]['name']} : ({planedata[0]['pos']},{planedata[1]['pos']},{planedata[2]['pos']}) \n x_axis: {xaxisdata[0]['name']} to {xaxisdata[1]['name']} :  ({xaxisdata[0]['pos']},{xaxisdata[1]['pos']})")
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