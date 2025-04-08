import argparse
import sys
from pathlib import Path
import csv
import json
import re
import requests 
from time import sleep
from requests.exceptions import RequestException
if __name__=="__main__":
    parentpath = Path(__file__).parent.parent.absolute()
    sys.path.append(str(parentpath))
from util.Configurator import Configurator

#adapted from https://sketchfab.com/developers/data-api/v3/python#example-python-model

MAX_RETRIES = 50
MAX_ERRORS = 10
RETRY_TIMEOUT = 10
def buildRequestPayload(*, data=None, files=None, json_payload=False):
    data = data or {}
    files = files or {}
    apikey = Configurator.getConfig().getProperty("postprocessing","sketchfab_api_key")
    headers = {"Authorization":f"Token {apikey}"}
    if json_payload:
        headers.update({"Content-Type":"application/json"})
        data = json.dumps(data)
    return {"data":data,"files":files,"headers":headers}

def uploadModel(zipfile, infodict):
    apiurl = Configurator.getConfig().getProperty("postprocessing","sketchfab_api_url")
    modelendpoint = f"{apiurl}/models"
    data = {
        "name":infodict["name"],
        "description":infodict["description"],
        "tags" : [],
        "categories":[],
        "isInspectable":True,
        "isPublished":False
    }
    with open(zipfile,"rb") as file_:
        files = {'modelFile':file_}
        payload = buildRequestPayload(data = data,files=files)
        try:
            response = requests.post(modelendpoint,**payload)
        except RequestException as e:
            print(f"Error:{e}")
            return
        if response.status_code==requests.codes.created:
            model_url = response.headers['Location']
            print(f"Model processing.\n When it's done, you'll be able to find it at {model_url}")
            return model_url
        else:
            print(f"Unexpected response: {response.status_code}.")
            return ""
    
def pollStatus(modelurl):
    errors = 0
    retry=0

    while (retry <= MAX_RETRIES and errors <=MAX_ERRORS):
        print("poling for model status.")
        payload = buildRequestPayload()
        try:
            response = requests.get(modelurl,**payload)
        except RequestException as e:
            print(f"Try failed with error {e}")
            errors+=1
            retry+=1
            continue
        result = response.json()
        if response.status_code != requests.codes.ok:
            error = result["error"]
            print(f"Upload failed with error:{error}")
            errors +=1
            retry+=1
            continue
        processing_status = result['status']['processing']
        if processing_status=='PENDING':
            print(f"In processing queue. Trying again in  {RETRY_TIMEOUT} seconds.")
            retry+=1
            sleep(RETRY_TIMEOUT)
            continue
        elif processing_status=="PROCESSING":
            print(f"Processing. Will check again in {RETRY_TIMEOUT} seconds")
            retry+=1
            sleep(RETRY_TIMEOUT)
            continue
        elif processing_status=="FAILED":
            print(f"Processing failed. {result['error']}")
            return False
        elif processing_status=="SUCCEEDED":
            print(f"Great success. Check the model here. {modelurl}")
            return True
        retry+=1
    print("Failed out due to too many errors or retries.")
    return False


def getModels(url,payload):
    response = requests.get(url,**payload)
    data = response.json()
    while data["next"]:
        yield data["results"]
        response = requests.get(data["next"],**payload)
        data = response.json()
def listModels():
    apiurl = Configurator.getConfig().getProperty("postprocessing","sketchfab_api_url")
    model_endpoint = f"{apiurl}/me/models"
    payload = buildRequestPayload()
    acc = []
    for res in getModels(model_endpoint,payload):
        acc = acc+res
    return acc
        
def descriptionToDict(desc:str):
    descdict = {}
    descarr =  desc.splitlines()
    repat = r"\**\s(?P<tkey>[\w\s]+):\s*(?P<tval>[\W\w]+)$"
    pat = re.compile(repat)
    for info in descarr:

        keyval = pat.match(info)
        if keyval and keyval.group('tkey') and keyval.group('tval'):
            print(f"{keyval.group('tkey')} : {keyval.group('tval')}")
            descdict[keyval.group('tkey').upper().replace(" ","")] = keyval.group('tval')
    return descdict


def getModelInfo(csvpath:Path):
    mdata = listModels()
    csvdata = []
    headernames = ["name","uid","embed url","creation date","category names","material","culture","provenance","registration","stable_url","photographer","modeler","tags"]
    for model in mdata:
        dsc = descriptionToDict(model["description"])
        categories =  ""
        categorynames = [c["name"] for c in model["categories"]]
        tags = [t["name"] for t in model["tags"]]

        modeldata = {
            "name": model["name"],
            "uid": model["uid"],
            "embed url":model["embedUrl"],
            "creation date": model["createdAt"],
            "tags" : ",".join(tags),
            "category names": ",".join(categorynames),
            "material":dsc["MATERIAL"] if "MATERIAL" in dsc.keys() else "",
            "culture":dsc["CULTURE"] if "CULTURE" in dsc.keys() else "",
            "provenance":dsc["PROVENANCE"] if "PROVENANCE" in dsc.keys() else "",
            "registration":dsc["ISACREGISTRATIONNUMBER"] if "ISACREGISTRATIONNUMBER" in dsc.keys() else "",
            "stable_url":dsc["MOREINFORMATION"] if "MOREINFORMATION" in dsc.keys() else "",
            "photographer":dsc["PHOTOGRAPHER"] if "PHOTOGRAPHER" in dsc.keys() else "",
            "modeler":dsc["IMAGEPROCESSINGANDMODELING"] if "IMAGEPROCESSINGANDMODELING" in dsc.keys() else ""
        }

        csvdata.append(modeldata)
    with open(csvpath,'w',encoding="utf-8") as f:
        headers = headernames #csvdata[0].keys()
        writer = csv.DictWriter(f,fieldnames = headers)
        writer.writeheader()
        writer.writerows(csvdata)
def command_upload(args):
    modelpath = Path(args.modelpath)
    infodict = {"name":args.name,"description":args.desc}
    if modelpath.exists():
        modelurl = uploadModel(modelpath,infodict)
        if modelurl:
            pollStatus(modelurl)

def command_GetModelInfo(args):
    csvpath = Path(args.csvpath)
    if csvpath.parent.exists():
        print("Got here. WTF is this error?")
        getModelInfo(csvpath)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(prog="SketchfabScripts")
    subparsers = parser.add_subparsers(help="Sub-command help")
    modelinfo = subparsers.add_parser("modelinfo", help="Gets tombstone data for all models and puts it in a csv file.")
    modelupload = subparsers.add_parser("upload",help="uploads a zipfile of a model to sketchfab")
    modelinfo.add_argument("csvpath", help="Filename and path for the csv file.", type=str)
    modelinfo.set_defaults(func=command_GetModelInfo)
    modelupload.add_argument("modelpath",help="The Path to a zipfile of a model.")
    modelupload.add_argument("name",help="The name that the model will have on sketchfab.")
    modelupload.add_argument("desc",help="A brief description of the model.")
    modelupload.set_defaults(func=command_upload)
    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()
