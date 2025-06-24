from pathlib import Path
import imageio
from os import mkdir,listdir
from tasks.BaseTask import BaseTask
from util import util
from PIL import Image as PILImage
import rawpy

from util.InstrumentationStatistics import *
from util.PipelineLogging import getLogger


class ConvertToJPG(BaseTask):

    def __init__(self, argdict:dict):
        super().__init__()
        self.input = Path(argdict["input"])
        self.output = Path(argdict["output"])

    def __repr__(self):
        return "Conversions: ConvertToJPG"
    
    def setup(self):
        super().setup()

        if not self.output.exists or not self.output.is_dir:
            mkdir(self.output)
        ret = True
        return ret
    

    def convert(self,fn:Path)->bool:
        success = True
        fp = fn.stem
        ipname = Path(self.input,fn)
        outputname = Path(self.output,f"{fp}.jpg")
        ext = fn.suffix.upper()
        if outputname.exists():
            return success
        try:
            if ext ==".CR2" or ext == ".NEF":
                print("Converting from RAW")
                with rawpy.imread(str(ipname)) as raw:
                    rgb = raw.postprocess(use_camera_wb=True)
                    imageio.imwrite(outputname,rgb)
            else:
                print("Converting from TIF")
                f=PILImage.open(ipname)
                rgb = f.convert('RGB')
                rgb.save(outputname,quality=95)

        except Exception as e:
            getLogger(__name__).error(e)
            success = False
        return success

    @timed(Statistic_Event_Types.EVENT_CONVERT_PHOTO)
    def execute(self)->bool:
        super().execute()
        success = True
        extns = [".TIF",".CR2",".NEF",]
        if self.input.is_file() and self.input.suffix.upper() in extns:
            success = self.convert(self.input)
        elif self.input.suffix.upper() == ".JPG":
             if self.input.parent != self.output:
                util.copy_file_to_dest(self.input,Path(self.output,self.input.name),False)
        return success
    
