from pathlib import Path
from os import mkdir
from tasks.BaseTask import BaseTask
from postprocessing import MeshlabHelpers
from util.Configurator import Configurator
from  util.InstrumentationStatistics import Statistic_Event_Types, timed

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
    
    def setup(self):
        #setup will fail if there is no blender installed at the path specified in config or if the input directory is not 
        #valid.
        ret = True
        super().setup()
        if not self.output.exists():
            mkdir(self.output)
        
        ret &= self.inputobj.exists() and self.inputobj.suffix ==".obj"
        ret &= self.blenderexec.exists()
        ret &= (self.scriptdir.exists() and self.scriptdir.is_dir())
        return ret

        
    
    @timed(Statistic_Event_Types.EVENT_SNAPSHOT)
    def execute(self)->bool:
        success = super().execute()
        try:
            scriptname = "snapshot_with_scale.py"
            script = Path(self.scriptdir,scriptname)
            rx = Configurator.getConfig().getProperty("postprocessing", "rot_x")
            ry = Configurator.getConfig().getProperty("postprocessing", "rot_y")
            rz = Configurator.getConfig().getProperty("postprocessing", "rot_z")
            params = {"input":str(self.inputobj),"render":str(self.output),"scale":self.usescale, "rx":rx, "ry":ry, "rz":rz}
            MeshlabHelpers.execute_blender_script(script,params)
        except Exception as e:
            success = False
            raise e
        return success
    
    def exit(self)->bool:
        filename = self.inputobj.stem
        return Path(self.inputobj.parent, f"{filename}_render.png").exists()

    
