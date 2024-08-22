import argparse
from pathlib import Path
import csv
import json
import re
import requests 
from requests.exceptions import RequestException

#adapted from https://sketchfab.com/developers/data-api/v3/python#example-python-model
CONFIG = {}
def loadConfig():
    with open("../config.json",'r',encoding='utf-8') as f:
        global CONFIG
        CONFIG = json.load(f)["config"]["postprocessing"]

def buildRequestPayload(*, data=None, files=None, json_payload=False):
    data = data or {}
    files = files or {}
    headers = {"Authorization":f"Token {CONFIG['sketchfab_api_key']}"}
    if json_payload:
        headers.update({"Content-Type":"application/json"})
        data = json.dumps(data)
    return {"data":data,"files":files,"headers":headers}

def listModels():
    model_endpoint = f"{CONFIG['sketchfab_api_url']}/me/models"
    payload = buildRequestPayload()
    try:
        response = requests.get(model_endpoint, **payload)
    except RequestException as e:
        print(f"An API Error occurred. {e}")
    else:
        data = response.json()
        if not len(data['results']) >0:
            print("There are no models to list.")
        print(len(data["results"]))
        return data["results"]
    
def descriptionToDict(desc:str):
    descdict = {}
    descarr =  desc.splitlines()
    repat = r"\**\s(?P<tkey>[\w\s]+):\s*(?P<tval>[\W\w]+)$"
    pat = re.compile(repat)
    for info in descarr:

        keyval = pat.match(info)
        if keyval and keyval.group('tkey') and keyval.group('tval'):
            print(f"{keyval.group('tkey')} : {keyval.group('tval')}")
            descdict[keyval.group('tkey')] = keyval.group('tval')
    return descdict


def getModelInfo(csvpath:Path):
    modeldata = listModels()
    csvdata = []
    for model in modeldata:
        dsc = descriptionToDict(model["description"])
        categories =  ""
        categorynames = [c["name"] for c in model["categories"]]
        tags = [t["name"] for t in model["tags"]]

        for t in model["tags"]:
            tags+=(f", {t['name']}")
        modeldata = {
            "name": model["name"],
            "uid": model["uid"],
            "embed Url":model["embedUrl"],
            "creation date": model["createdAt"],
            "tags" : ",".join(tags),
            "category names": ",".join(categorynames)
        }
        modeldata["tags"] = tags
        modeldata.update(dsc)
        csvdata.append(modeldata)
    with open(csvpath,'w',encoding="utf-8") as f:
        headers = csvdata[0].keys()
        writer = csv.DictWriter(f,fieldnames = headers)
        writer.writeheader()
        writer.writerows(csvdata)

def command_GetModelInfo(args):
    csvpath = Path(args.csvpath)
    if csvpath.parent.exists():
        print("Got here. WTF is this error?")
        getModelInfo(csvpath)

if __name__ == "__main__":
    loadConfig()
    parser = argparse.ArgumentParser(prog="SketchfabScripts")
    subparsers = parser.add_subparsers(help="Sub-command help")
    modelinfo = subparsers.add_parser("modelinfo", help="Gets tombstone data for all models and puts it in a csv file.")
    modelinfo.add_argument("csvpath", help="Filename and path for the csv file.", type=str)
    modelinfo.set_defaults(func=command_GetModelInfo)
    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()
