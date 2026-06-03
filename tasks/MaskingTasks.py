from os import mkdir
from pathlib import Path
import shutil
import subprocess
import cv2
import requests
from inference_sdk import InferenceHTTPClient
from PIL import Image,ImageDraw
from util.InstrumentationStatistics import *
from util.PipelineLogging import getLogger
from util.Configurator import Configurator
from util.ErrorCodeConsts import ErrorCodes
from tasks.BaseTask import BaseTask,TaskStatus


class MaskImages(BaseTask):
    def __init__(self, argdict:dict):
        super().__init__()
        self.input = Path(argdict["input"])
        self.output = Path(argdict["output"])

    def setup(self)->tuple[bool,ErrorCodes]:
        success,code = super().setup()
        if success:
            success= (Path(self.input).exists())
            if not success:
                getLogger(__name__).error("Input Path %s does not exist.",self.input)
                success = False
                code = ErrorCodes.INVALID_FILE
            else:
                outputpath = Path(self.output)
                if not outputpath.exists():
                    mkdir(outputpath)
        return success,code
    
    def build_mask(self,fn:Path)->tuple[bool,ErrorCodes]:
        return True,ErrorCodes.NONE
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MASK)
    def execute(self)->tuple[bool,ErrorCodes]:
        success,code = super().execute()
        if success:
            extns = [".JPG",".TIF"]
            if self.input.is_file() and self.input.suffix.upper() in extns:
                if not Path(self.output,f"{self.input.stem}.png").exists():
                    success, code = self.build_mask(self.input)
            else:
                success = False
                code = ErrorCodes.INVALID_FILE
        return success,code
        
    def exit(self)->tuple[bool,ErrorCodes]:
        success, code = super().exit()
        if success:
            getLogger(__name__).info("Verifying masks were created")
            maskname = Path(self.output,f"{self.input.stem}.png")
            if not maskname.exists():
                success = False
                code = ErrorCodes.MASK_CREATION_FAILURE
                getLogger(__name__).info("Could not find mask for %s as %s", self.input,maskname)
        return success,code
class MaskIntersection(MaskImages):
    """Builds a mask that is the intersection of two other masks. FINISH IMPLEMENTING THIS"""
    def __init__(self,argdict:dict):
        super().__init__(argdict)
        self.mask1 = argdict["mask1"]
        self.mask2 = argdict["mask2"]
    def __repr__(self):
        return "Masking: Two Mask Intersection"

    
class MaskThreshold(MaskImages):
    """Uses grayscale thresholding to build a mask of the object. Basically, converts each picture to grayscale and then takes all values
    below a certain cutoff point and makes them black while making all pixels above the cutoff point white. You can set this cutoff point by
    changing the thresholding_lower_gray_threshold value in config.json if you are not getting results you like. This should be a value between 0 and 255.
    For this method to work well, you should have good control over the lighting in your photographs and have a background and turntable that are white."""

    def __init__(self, argdict:dict):
        super().__init__(argdict)
        self.greythreshold = Configurator.getConfig().getProperty("processing","thresholding_lower_gray_threshold")

    def __repr__(self):
        return "Masking: MaskThreshold"
    
    def setup(self):
        success,code = super().setup()
        if  success:
            self.greythreshold = max(0,min(self.greythreshold,255)) #clamp this value between 0 and 255
        return success,code
    

    def build_mask(self,fn:Path):
        success,code = super().build_mask(fn)
        try:
            picpath = Path(self.input,fn)
            maskout = Path(self.output,f"{fn.stem}.png")
            img = cv2.imread(str(picpath))
            #threshold image
            grayscale = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
            mask = cv2.threshold(grayscale,self.greythreshold,255,cv2.THRESH_BINARY)[1]
            mask = 255-mask #invert the colors
            cv2.imwrite(str(maskout),mask)
        except cv2.error as e:
            getLogger(__name__).error(e)
            success = False
            code = ErrorCodes.MASK_CREATION_FAILURE
        return success,code

        
class MaskDroplet(MaskImages):
    """Builds a mask of an image using either a user specified photoshop droplet or the one in utils. You can configure
    which droplet to use in config.json under processing->SmartSelectDroplet. You need to make that droplet save to a specific directorym, which will be configured in the droplet, and 
    also in config.json under processing->Droplet_Output. This is generally the slowest way to do masking and requires that the object is positioned over the center pixel
    when the photograph is taken. It generally does the most accurate maksing job for the widest variety of objects, but takes about 5 times as much time as the
    Docker Roboflow-inference method and about 16 times as long as thresholding."""

    def __init__(self, argdict:dict):
        super().__init__(argdict)
        self.dropletoutput = Path(Configurator.getConfig().getProperty("processing","Droplet_Output"))
        self.dropletpath = Path(Configurator.getConfig().getProperty("processing","SmartSelectDroplet"))

    def __repr__(self):
        return "Masking: MaskDroplet"
    
    def setup(self):
        success,code = super().setup()
        if success:
            if not self.dropletpath.exists():
                getLogger(__name__).error("Invalid droplet path, %s", self.dropletpath)
                return False,ErrorCodes.CONFIGURATION_ERROR
            getLogger(__name__).info("Using Droplet at %s to process photos in %s", self.dropletpath,self.input)
            if not self.dropletoutput.exists():
                mkdir(self.dropletoutput)
        return success,code

    def build_mask(self, fn:Path):
        success,code = super().build_mask(fn)
        if success:
            subprocess.run([str(self.dropletpath),Path(self.input,fn)],check = False)
            newmask = Path(self.dropletoutput,f"{fn.stem}.png")
            maskpath = Path(self.output,f"{fn.stem}.png")
            if newmask.exists():
                shutil.move(newmask,maskpath)
            else:
                success = False
                code = ErrorCodes.MASK_CREATION_FAILURE
            shutil.rmtree(self.dropletoutput)
        return success,code
    

    
class MaskAI(MaskImages):

    """Uses a trained segmentation model on roboflow called "pot_or_not", hosted locally in a docker container 
    to infer the location of a pot in the picture. It will then mask out the location of the object based on where the inference
    algorithm thinks there's a pot. This works best with pots and should take about 1/5 the time as the same operation in photoshop
    However, it does require that the user have the inference engine running on a local server on port 9001, a roboflow API key set
    in an environment variable ROBOFLOW_KEY, and access to the pot_or_not/2 model. For help setting up the docker container, see the 
    roboflow documentation here: https://inference.roboflow.com/quickstart/docker/"""
    

    def __init__(self,argdict:dict):
        self.apikey = Configurator.getConfig().getProperty("processing","Roboflow_API_Key")
        self.serverurl = "http://localhost:9001"
        self.model = "pot_or_not/3"
        super().__init__(argdict)
    
    def __repr__(self):
        return "Masking: MaskAI"
    
    def setup(self):
        #check to see if server is up and responsive.
        success,code = super().setup()
        if success:
            url = ("http://localhost:9001")
            try:
                response = requests.get(url,timeout=2)
                ret = (response.status_code == 200)
            except requests.exceptions.RequestException as e:
                success = False
                getLogger(__name__).error(e)
            if not success:
                getLogger(__name__).error("Could not connect to the roboflow docker container on localhost port 9001. Please set up or start the server.")
                code = ErrorCodes.INFERENCE_ENGINE_FAILURE
            if self.apikey is None or self.apikey == "":
                getLogger(__name__).error("Invalid API key. Please set an environment variable ROBOFLOW_KEY in the shell.")
                ret = False
                code = ErrorCodes.CONFIGURATION_ERROR
        return success,code
    

    def infer_and_snip(self,fn:Path, inferenceclient:InferenceHTTPClient):
        success = True
        code = ErrorCodes.NONE
        potprediction = {}             
        picpath = Path(self.input,fn)
        potprediction = inferenceclient.infer(str(picpath))
        pots = []
        holes=[]
        for prediction in potprediction["predictions"]:
            shape = [(point['x'],point['y']) for point in prediction["points"]]
            if prediction["class"]=="pot":              
                pots.append(shape)
            elif prediction["class"]=="hole":
                holes.append(shape)

        with Image.open(picpath).convert('RGB') as pmask:
            draw = ImageDraw.Draw(pmask)
            draw.rectangle([(0,0),pmask.size],fill=(0,0,0))
            for pot in pots:
                draw.polygon(pot,fill=(255,255,255))
            for hole in holes:
                draw.polygon(hole,fill=(0,0,0))
            outpicpath = Path(self.output,f"{fn.stem}.png")
            pmask.save(outpicpath)

        return success,code
    
    def execute(self):
        success = True
        code = ErrorCodes.NONE
        self._status = TaskStatus.RUNNING
        getLogger(__name__).info("Executing %s",self._statename)
        success = True
        client = InferenceHTTPClient(api_url = self.serverurl,
                                     api_key = self.apikey)
        client.load_model(self.model,set_as_default=True)
        getLogger(__name__).info("Building masks for files in %s and leaving the results in %s", self.input, self.output)
        extns = [".JPG",".TIF"]
        if self.input.is_file() and self.input.suffix.upper() in extns:
            maskname =  Path(self.output,f"{self.input.stem}.png")
            if not maskname.exists():
                self.infer_and_snip(self.input,client)
        return success,code

