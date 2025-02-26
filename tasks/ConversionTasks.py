from pathlib import Path
import imageio
from os import mkdir,listdir
from tasks.BaseTask import BaseTask
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
        ret = False
        super().setup()
        if self.input.exists and self.input.is_dir:
            if not self.output.exists or not self.output.is_dir:
                mkdir(self.output)
            ret = True
        return ret
    
    @timed(Statistic_Event_Types.EVENT_CONVERT_PHOTO)
    def execute(self)->bool:
        super().execute()
        success = True
        extns = [".TIF",".CR2",".NEF"]
        print(self.input)
    
        for fn in [Path(f) for f in listdir(self.input) if Path(f).suffix.upper() in extns]:
            if not self._shouldFinish:
                fp = fn.stem
                ipname = Path(self.input,fn)
                outputname = Path(self.output,f"{fp}.jpg")
                ext = fn.suffix.upper()
                if outputname.existS():
                    continue
                try:
                    if ext ==".CR2" or ext == ".NEF":
                        print("Converting from RAW")
                        with rawpy.imread(ipname) as raw:
                            rgb = raw.postprocess(use_camera_wb=True)
                            imageio.imwrite(outputname,rgb)
                    else:
                        print("Converting from TIF")
                        f=PILImage.open(ipname)
                        rgb = f.convert('RGB')
                        rgb.save(outputname,quality=95)
                except Exception as e:
                    getLogger(__name__).error(e)
                    self._shouldFinish = True
                    success = False
        return success
    
