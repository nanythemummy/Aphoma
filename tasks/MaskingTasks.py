from os import environ, mkdir,listdir
from pathlib import Path
import requests
import shutil
import subprocess

from PIL import Image,ImageDraw
from util.InstrumentationStatistics import *
from util.PipelineLogging import getLogger
from util.Configurator import Configurator
from tasks.BaseTask import *
import cv2
from inference_sdk import InferenceHTTPClient

class MaskImages(BaseTask):
    def __init__(self, argdict:dict):
        super().__init__()
        self.maskingmode = argdict["maskoption"]
        self.input = Path(argdict["input"])
        self.output = Path(argdict["output"])

    def setup(self):
        success = super().setup()
        if success:
            success= (Path(self.input).exists())
            if not success:
                getLogger(__name__).error("Input Path %s does not exist.",self.input)
            else:
                outputpath = Path(self.output)
                if not outputpath.exists():
                    mkdir(outputpath)
        return success
    
    def build_mask(self,fn:Path):
        pass

    def execute(self):
        success = super().execute()
        if not success:
            return False
        extns = [".JPG",".TIF"]
        for fn in [Path(f) for f in listdir(self.input) if Path(f).suffix.upper() in extns]:
            if not Path(self.output,f"{fn.stem}.png").exists():
                self.build_mask(fn)
        return True
        
    def exit(self):
        success = True
        extns = [".JPG",".TIF"] 
        getLogger(__name__).info("Verifying masks were created")
        for fn in [Path(f) for f in listdir(self.input) if Path(f).suffix.upper() in extns]:
            maskname = Path(self.output,f"{fn.stem}.png")
            if not maskname.exists():
                success = False
                getLogger(__name__).info("Could not find mask for %s as %s", fn,maskname)
                break
        return success
    
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
        success = super().setup()
        if not success:
            return False
        self.greythreshold = max(0,min(self.greythreshold,255)) #clamp this value between 0 and 255
        return True
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MASK)
    def build_mask(self,fn:Path):
        picpath = Path(self.input,fn)
        maskout = Path(self.output,f"{fn.stem}.png")
        img = cv2.imread(str(picpath))
        #threshold image
        grayscale = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        mask = cv2.threshold(grayscale,self.greythreshold,255,cv2.THRESH_BINARY)[1]
        mask = 255-mask #invert the colors
        cv2.imwrite(str(maskout),mask)


        
class MaskDroplet(MaskImages):
    """Builds a mask of a whole folder of images using either a user specified photoshop droplet or the one in utils. You can configure
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
        success = super().setup()
        if not success:
            return False
        if not self.dropletpath.exists():
            getLogger(__name__).error("Invalid droplet path, %s", self.dropletpath)
            return False
        getLogger(__name__).info("Using Droplet at %s to process photos in %s", self.dropletpath,self.input)

        maskdir = self.output
        if not maskdir.exists():
            mkdir(maskdir)
        if not self.dropletoutput.exists():
            mkdir(self.dropletoutput)
        return True
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MASK)
    def build_mask(self, fn:Path):
        subprocess.run([str(self.dropletpath),Path(self.input,fn)],check = False)
        newmask = Path(self.dropletoutput,f"{fn.stem}.png")
        maskpath = Path(self.output,f"{fn.stem}.png")
        if newmask.exists():
            shutil.move(newmask,maskpath)
        else:
            return False
        return True
    
    def exit(self):
        success = super().execute()
        if not success:
            return False
        shutil.rmtree(self.dropletoutput)
        return True
    
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
        ret = super().setup()
        if ret:
            url = ("http://localhost:9001")
            try:
                response = requests.get(url,timeout=2)
                ret = response.status_code == 200
            except requests.exceptions.RequestException as e:
                ret = False
                getLogger(__name__).error(e)
            if not ret:
                getLogger(__name__).error("Could not connect to the roboflow docker container on localhost port 9001. Please set up or start the server.")
            if self.apikey is None or self.apikey == "":
                getLogger(__name__).error("Invalid API key. Please set an environment variable ROBOFLOW_KEY in the shell.")
                ret = False
        return ret
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MASK)
    def build_mask(self,fn:Path, inferenceclient:InferenceHTTPClient):
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

    def execute(self):
        "Need to do this because I'm fully overriding baseclass functionality here."
        self._status = TaskStatus.RUNNING
        getLogger(__name__).info("Executing %s",self._statename)
        success = True
        client = InferenceHTTPClient(api_url = self.serverurl,
                                     api_key = self.apikey)
        client.load_model(self.model,set_as_default=True)
        getLogger(__name__).info("Building masks for files in %s and leaving the results in %s", self.input, self.output)
        extns = [".JPG",".TIF"]
        for fn in [Path(f) for f in listdir(self.input) if Path(f).suffix.upper() in extns]:
            maskname =  Path(self.output,f"{fn.stem}.png")
            if not maskname.exists():
                self.build_mask(fn,client)
        return success

