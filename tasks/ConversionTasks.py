from pathlib import Path
import imageio
from os import mkdir,listdir
from tasks.BaseTask import BaseTask
from PIL import Image as PILImage
import rawpy

from util.InstrumentationStatistics import InstrumentationStatistics, Statistic_Event_Types
from util.PipelineLogging import getLogger


class ConvertToJPG(BaseTask):
    
    def __init__(self, argdict:dict):
        super().__init__("ConvertToJPG")
        self.input = Path(argdict["input"])
        self.output = Path(argdict["output"])

    def setup(self):
        ret = False
        super().setup()
        if self.input.exists and self.input.is_dir:
            if not self.output.exists or not self.output.is_dir:
                mkdir(self.output)
            ret = True
        return ret
    
    def execute(self)->bool:
        sid = InstrumentationStatistics.getStatistics().timeEventStart(Statistic_Event_Types.EVENT_CONVERT_PHOTO)
        super().execute()
        success = False
        extns = [".TIF",".CR2",".NEF"]
        print(self.input)
        for fn in [Path(f) for f in listdir(self.input) if Path(f).suffix.upper() in extns]:
            if not self._shouldFinish:
                fp = fn.stem
                ipname = Path(self.input,fn)
                outputname = Path(self.output,f"{fp}.jpg")
                ext = fn.suffix.upper()
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
        InstrumentationStatistics.getStatistics().timeEventEnd(sid)
        return success
    
    def exit(self)->bool:
        super().exit()