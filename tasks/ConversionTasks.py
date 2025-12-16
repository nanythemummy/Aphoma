from pathlib import Path
import imageio
from os import mkdir,remove

from PIL import Image as PILImage
from tasks.BaseTask import BaseTask
from util import util
from util.ErrorCodeConsts import ErrorCodes
from util.Configurator import Configurator
import subprocess

import rawpy

from util.InstrumentationStatistics import *
from util.PipelineLogging import getLogger

class ConvertToTIF(BaseTask):
    '''Each of these requires a dictionary with {"input":string and "output":string}, 
    the first is the file you want to convert with its extension
    the second is the directory you want to save it in. The task converts the input file to a tif, and the exit function confirms that this happened
    by checking if there is an jpg with the input filename in the output directory'''

    def __init__(self, argdict:dict):
        super().__init__()
        self.input = Path(argdict["input"])
        self.output = Path(argdict["output"])

    def __repr__(self):
        return "Conversions: ConvertToTIF"
    
    def setup(self):
        success,code =super().setup()
        if success:
            if not self.output.exists or not self.output.is_dir:
                mkdir(self.output)
        return success,code
    
    def convert(self,fn:Path)->bool:
        success = True
        fp = fn.stem
        ipname = Path(self.input,fn)
        outputname = Path(self.output,f"{fp}.tif")
        ext = fn.suffix.upper()
        if outputname.exists():
            return success
        try:
            if ext ==".CR2" or ext == ".NEF":
                print("Converting from RAW")
                exiftoolpath = Configurator.getConfig().getProperty("processing","Exiftool_Path")
                with rawpy.imread(str(ipname)) as raw:
                    rgb = raw.postprocess(use_camera_wb=True)
                    imageio.imwrite(outputname,rgb)
                if Path(exiftoolpath).exists():
                    cmd = f"\"{exiftoolpath}\" -tagsFromFile \"{ipname}\" \"{outputname}\""
                    print(cmd)
                    subprocess.run(cmd,shell=True,check = False)
                    backup = Path(f"{outputname}_original")
                    if backup.exists():
                        remove(backup)
                    
            else:
                print("Converting from JPG")
                f=PILImage.open(ipname)
                rgb = f.convert('RGB')
                rgb.save(outputname)

        except Exception as e:
            getLogger(__name__).error(e)
            success = False
        return success

    @timed(Statistic_Event_Types.EVENT_CONVERT_PHOTO)
    def execute(self)->tuple[bool,ErrorCodes]:
        success,code =super().execute()
        if success:
            extns = [".JPG",".CR2",".NEF",]
            if self.input.is_file() and self.input.suffix.upper() in extns:
                success = self.convert(self.input)
                if not success:
                    code = ErrorCodes.FILE_CONVERSION_FAILURE

            elif self.input.suffix.upper() == ".TIF":
                if self.input.parent != self.output:
                    util.copy_file_to_dest(self.input,Path(self.output,self.input.name),False)
            else:
                success = False
                code = ErrorCodes.INVALID_FILE
        return success,code
    
    def exit(self):
        success,code = super().exit()
        if success:
            if not Path(self.output,f"{self.input.stem}.tif").exists():
                code = ErrorCodes.FILE_CONVERSION_FAILURE        
                success = False
        return success,code


class ConvertToJPG(BaseTask):
    '''Each of these requires a dictionary with {"input":string and "output":string}, 
    the first is the file you want to convert with its extension
    the second is the directory you want to save it in. The task converts the input file to a jpg, and the exit function confirms that this happened
    by checking if there is an jpg with the input filename in the output directory'''

    def __init__(self, argdict:dict):
        super().__init__()
        self.input = Path(argdict["input"])
        self.output = Path(argdict["output"])

    def __repr__(self):
        return "Conversions: ConvertToJPG"
    
    def setup(self):
        success,code =super().setup()
        if success:
            if not self.output.exists or not self.output.is_dir:
                mkdir(self.output)
        return success,code
    

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
    def execute(self)->tuple[bool,ErrorCodes]:
        success,code =super().execute()
        if success:
            extns = [".TIF",".CR2",".NEF",]
            if self.input.is_file() and self.input.suffix.upper() in extns:
                success = self.convert(self.input)
                if not success:
                    code = ErrorCodes.FILE_CONVERSION_FAILURE
            elif self.input.suffix.upper() == ".JPG":
                if self.input.parent != self.output:
                    util.copy_file_to_dest(self.input,Path(self.output,self.input.name),False)
            else:
                success = False
                code = ErrorCodes.INVALID_FILE
        return success,code
    
    def exit(self):
        success,code = super().exit()
        if success:
            outputpath = Path(self.output,f"{self.input.stem}.jpg")
            if not outputpath.exists():
                code = ErrorCodes.FILE_CONVERSION_FAILURE     
                success = False   
        return success,code


