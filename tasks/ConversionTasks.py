
from os import mkdir, makedirs
from pathlib import Path
import rawpy
import imageio
import numpy
import lensfunpy
import cv2
from PIL import Image as PILImage
from tasks.BaseTask import BaseTask
from util import util
from util.ErrorCodeConsts import ErrorCodes
from util.Configurator import Configurator 



from util.InstrumentationStatistics import *
from util.PipelineLogging import getLogger

class ConvertToTask(BaseTask):
    def __init__(self, argdict:dict):
        super().__init__()
        self.input = Path(argdict["input"])
        self.output = Path(argdict["output"])
        self.profile_correction = bool(argdict.get("profile_correction",False))
    def setup(self):
        success,code =super().setup()
        if success:
            if not self.output.exists() or not self.output.is_dir():
                makedirs(self.output)
        return success,code
    def profileCorrection(self, tifhandle): #tifhandle needs to be a cv2 numpy array
        if self.profile_correction:
            cam = Configurator.getConfig().getProperty("processing","Camera")
            lens = Configurator.getConfig().getProperty("processing","Lens")
            #do lens profile correction This code was borrowed from here: https://pypi.org/project/lensfunpy/
            exif = util.get_exif_data(self.input)
            clprofile = util.get_camera_lens_profile(cam,lens)
            cam_make = exif.get("Make",clprofile["camera"]["maker"])
            cam_model = exif.get("Model",clprofile["camera"]["model"])
            lens_model = exif.get("Lens",clprofile["lens"]["model"])
            lens_make = clprofile["lens"]["maker"]
            lensdb = lensfunpy.Database()
            #both of these return a list, the first item of which should be our camera. If not, we need to be more specific.
            caminfo = lensdb.find_cameras(cam_make,cam_model)[0]
            lensinfo = lensdb.find_lenses(caminfo,lens_make,lens_model)[0]
            #get data needed for calc from exif data
            
            focal_length = exif["FocalLength"] if "FocalLength" in exif.keys() else 0
            aperture = exif["FNumber"] if "FNumber" in exif.keys() else 0
        

            if focal_length ==0 or aperture ==0:
                getLogger(__name__).error("WARNING: Can't do profile corrections, because there is no value for aperture or f-number in the exif data of the photo.")
                return tifhandle
            distance = 1.0 #can't think of a great way to calculate this so I'm going to hardcode it since it's about a meter in person and with the ortery.
            img_width = tifhandle.shape[1]
            img_height = tifhandle.shape[0]
            modifier = lensfunpy.Modifier(lensinfo,caminfo.crop_factor,img_width,img_height)
            print(f"focal_length = {focal_length}, aperture ={aperture}, distance={distance}, cam:{caminfo}, lens:{lensinfo}")
            modifier.initialize(focal_length,aperture,distance,pixel_format = tifhandle.dtype.type ) #demo code has this as just dtype, but it has a keyerror exception.
            undist_coords = modifier.apply_geometry_distortion()
            newimg = cv2.remap(tifhandle,undist_coords, None, cv2.INTER_LANCZOS4)
            if not modifier.apply_color_modification(newimg):
                getLogger(__name__).error("WARNING: Failed to remove vignetting.")
            return newimg
        else:
            return tifhandle
class ConvertToTIF(ConvertToTask):
    
    '''Each of these requires a dictionary with {"input":string and "output":string}, 
    the first is the file you want to convert with its extension
    the second is the directory you want to save it in. The task converts the input file to a tif, and the exit function confirms that this happened
    by checking if there is an jpg with the input filename in the output directory'''



    def __repr__(self):
        return "Conversions: ConvertToTIF"
    


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
                corrected = None
                with rawpy.imread(str(ipname)) as raw:
                    if not self.profile_correction:
                        rgb = raw.postprocess(use_camera_wb=True)
                    else:
                        rgb = raw.postprocess(use_camera_wb=True,
                                              use_auto_wb = False,
                                              output_color = rawpy.ColorSpace.sRGB, 
                                              output_bps=16,
                                              user_flip=0,
                                              user_black=None,
                                              user_sat = None)
                    #corrected = self.profileCorrection(rgb)
                imageio.imwrite(outputname,rgb)

            else:
                print("Converting from JPG")
                f=PILImage.open(ipname)
                rgb = f.convert('sRGB')
                rgb.save(outputname)
            util.copy_exif_data(ipname,outputname)

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


class ConvertToJPG(ConvertToTask):
    '''Each of these requires a dictionary with {"input":string and "output":string}, 
    the first is the file you want to convert with its extension
    the second is the directory you want to save it in. The task converts the input file to a jpg, and the exit function confirms that this happened
    by checking if there is an jpg with the input filename in the output directory'''


    def __repr__(self):
        return "Conversions: ConvertToJPG"
    
    

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
                    corrected = self.profileCorrection(rgb)
                    im = PILImage.fromarray(corrected)
                    im.save(outputname)
            else:
                print("Converting from TIF")
                f=PILImage.open(ipname)
                rgb = f.convert('RGB')
                rgb.save(outputname,quality=95)
            util.copy_exif_data(ipname,outputname)
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


