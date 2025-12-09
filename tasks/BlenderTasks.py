from pathlib import Path
from os import mkdir
from tasks.BaseTask import BaseTask
from postprocessing import MeshlabHelpers
from util.Configurator import Configurator
from  util.InstrumentationStatistics import Statistic_Event_Types, timed
from util.ErrorCodeConsts import ErrorCodes

class BlenderSnapshotTask(BaseTask):
    """
    Takes an obj file and takes a snapshot of it using blender. It also creates a scale next to the object.
    Requires a dict of args with the keys:
    inputobj -- the full path to the obj file.
    output -- the directory to store the output and intermediary files.
    scale -- should include scale, boolean.
    Rotation and scalesize can be set in config.json under postprocessing or via the ui.
    """

    def __init__(self, argdict:dict):
        super().__init__()
        self.inputobj = Path(argdict["inputobj"])
        self.output = Path(argdict["output"])
        self.scriptdir = Path(Configurator.getConfig().getProperty("postprocessing","script_directory"))
        self.blenderexec = Path(Configurator.getConfig().getProperty("postprocessing","blender_exec"))
        self.usescale = argdict["scale"]

    def __repr__(self):
        return "Blender: Snapshot"
    
    def setup(self)->tuple:
        #setup will fail if there is no blender installed at the path specified in config or if the input directory is not 
        #valid.
        success,code = super().setup()
        if success:
            if not self.output.exists():
                mkdir(self.output)
            
            if not self.inputobj.exists() and self.inputobj.suffix ==".obj":
                return False, ErrorCodes.INVALID_FILE
                
            if not self.blenderexec.exists():
                return False, ErrorCodes.EXTERNAL_EXECUTABLE_MISSING

            if not self.scriptdir.exists() or not self.scriptdir.is_dir():
                return False, ErrorCodes.INVALID_BLENDER_SCRIPT_DIRECTORY
        return success,code

        
    
    @timed(Statistic_Event_Types.EVENT_SNAPSHOT)
    def execute(self)->tuple:
        success,code = super().execute()
        if success:
            try:
                scriptname = "snapshot_with_scale.py"
                script = Path(self.scriptdir,scriptname)
                rx = Configurator.getConfig().getProperty("postprocessing", "rot_x")
                ry = Configurator.getConfig().getProperty("postprocessing", "rot_y")
                rz = Configurator.getConfig().getProperty("postprocessing", "rot_z")
                params = {"input":str(self.inputobj),"render":str(self.output),"scale":self.usescale, "rx":rx, "ry":ry, "rz":rz}
                MeshlabHelpers.execute_blender_script(script,params)
            except Exception:
                success = False
                code = ErrorCodes.BLENDER_SCRIPT_FAILURE
        return success,code
    
    def exit(self)->tuple:
        success,code = super().exit()
        if success:
            filename = self.inputobj.stem
            if not Path(self.inputobj.parent, f"{filename}_render.png").exists():
                success = False
                code = ErrorCodes.INVALID_FILE
        return success,code

    
