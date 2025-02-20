from os import environ, mkdir,listdir
from pathlib import Path
import requests
import shutil
import subprocess
from inference_sdk import InferenceHTTPClient
from PIL import Image,ImageDraw
from util.InstrumentationStatistics import InstrumentationStatistics, Statistic_Event_Types
from util.PipelineLogging import getLogger
from util.Configurator import Configurator
from tasks.BaseTask import BaseTask

class MaskImages(BaseTask):
    def __init__(self, argdict:dict):
        super().__init__("Masking")
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
    def exit(self):
        success = True
        extns = [".JPG",".TIF"] 
        for fn in [Path(f) for f in listdir(self.input) if Path(f).suffix.upper() in extns]:
            maskname = Path(self.output,f"{fn.stem}.png")
            if not maskname.exists():
                success = False
                getLogger(__name__).info("Could not find mask for %s as %s", fn,maskname)
                break
        return success
    
class MaskDroplet(MaskImages):

    def __init__(self, argdict:dict):
        super().__init__(argdict)
        self.dropletoutput = Path(Configurator.getConfig().getProperty("processing","Droplet_Output"))
        self.dropletpath = Path(Configurator.getConfig().getProperty("processing","SmartSelectDroplet"))

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
    
    def execute(self):
        sid = InstrumentationStatistics.getStatistics().timeEventStart(Statistic_Event_Types.EVENT_BUILD_MASK)
        success = super().execute()
        if not success:
            return False
        subprocess.run([str(self.dropletpath),str(self.input)],check = False)
        for f in listdir(self.dropletoutput): #scans through a given directory, returning an interator.
            fname = Path(self.dropletoutput,f)
            if fname.exists():
                newpath = Path(self.output,f)
                shutil.move(fname,newpath)
        InstrumentationStatistics.getStatistics().timeEventEnd(sid)
        return True
    
    def exit(self):
        success = super().execute()
        if not success:
            return False
        shutil.rmtree(self.dropletoutput)
    
class MaskAI(MaskImages):
    def __init__(self,argdict:dict):
        self.apikey = environ["ROBOFLOW_KEY"]
        self.serverurl = "http://localhost:9001"
        self.model = "pot_or_not/2"
        super().__init__(argdict)
    
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
    
    def execute(self):
        super().execute()
        success = True
        client = InferenceHTTPClient(api_url = self.serverurl,
                                     api_key = self.apikey)
        client.load_model(self.model,set_as_default=True)
        extns = [".JPG",".TIF"]
        getLogger(__name__).info("Building masks for files in %s and leaving the results in %s", self.input, self.output)
        try:
            for fn in [Path(f) for f in listdir(self.input) if Path(f).suffix.upper() in extns]:
                potprediction = {}
                sid = InstrumentationStatistics.getStatistics().timeEventStart(Statistic_Event_Types.EVENT_BUILD_MASK)
                picpath = Path(self.input,fn)
                potprediction = client.infer(str(picpath))
                for prediction in potprediction["predictions"]:
                    if prediction["class"]=="pot":
                        pots = []
                        potshape = [(point['x'],point['y']) for point in prediction["points"]]
                        pots.append(potshape)
                with Image.open(picpath).convert('RGB') as pmask:
                    draw = ImageDraw.Draw(pmask)
                    draw.rectangle([(0,0),pmask.size],fill=(0,0,0))
                    for pot in pots:
                        draw.polygon(pot,fill=(255,255,255))
                    outpicpath = Path(self.output,f"{fn.stem}.png")
                    pmask.save(outpicpath)
                InstrumentationStatistics.getStatistics().timeEventEnd(sid)
        except Exception as e:
            success = False
            getLogger(__name__).error(e)
        return success

