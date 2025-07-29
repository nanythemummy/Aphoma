import sys
import argparse
import os
import shutil
from pathlib import Path
import json, csv, re
from datetime import date
if __name__=="__main__":
    parentpath = Path(__file__).parent.parent.absolute()
    sys.path.append(str(parentpath))
from util.PipelineLogging import getLogger as getGlobalLogger
from util.Configurator import Configurator
from util.util import get_export_filename

#makes a zipfile from a set of files.
def zipTheseFiles(files:list, basedir:Path, zipfilename:str):
    file_existed = False
    try:
        zipdir = Path(basedir,zipfilename)
        if not Path(zipdir,".zip").exists():
            os.mkdir(zipdir)
        for f in files:
            shutil.copy2(f,Path(zipdir,Path(f).name))
        shutil.make_archive(zipdir,"zip",zipdir)
    except shutil.Error as e:
        getGlobalLogger(__name__).error(e)
        raise e
    except FileExistsError as e:
        getGlobalLogger(__name__).error(e)
        file_existed=True
        raise e
    finally:
        if not file_existed:
            shutil.rmtree(Path(basedir,zipfilename))

def parseObjFiles(filename:str):
    dependencies = []
    dependencies.append(filename)
    mtllib = re.compile(r"^mtllib\s(.+\.mtl)\s*$")
    texfile = re.compile(r"^map_Kd\s(.+\.png)\s*$")
    mtlfile = ""
    mtlfileappended = False
    with open(filename,'r',buffering=1,encoding="utf-8") as objfile:
        line= objfile.readline()
        while line:
            matches = re.fullmatch(mtllib,line)
            if matches:
                mtlfile = Path(Path(filename).parent,matches[1])
                if mtlfile.exists():
                    dependencies.append(mtlfile)
                    mtlfileappended=True
                break
            line = objfile.readline()
    if mtlfileappended:
        with open(mtlfile,"r",encoding="utf-8") as f:
            line = f.readline()
            while line:
                filematch = re.match(texfile,line)
                if filematch:
                    texfilepath = Path((Path(filename).parent),filematch[1])
                    if texfilepath.exists():
                        dependencies.append(texfilepath)
                line = f.readline()
    return dependencies
def generateEmuCSV(modeldict):
    models = []
    for k,v in modeldict.items():
        model= {"MulTitle":k,
                "MulDescription":v["description"],
                "Multimedia":v["multimedia"],
                "MulResourceType_tab(1)":"Registration Number",
                "MulIndentifyingNumber_tab(1)":v["registration"],
                "MulResourceType_tab(2)":"Sketchfab 3D Model",
                "MulIdentifyingNumber_tab(2)":v["sketchfab"],
                "MulPartyRef_tab(1).NamFirst":v["creator"]["first"],
                "MulPartyRef_tab(1).NamLast":v["creator"]["last"],
                "MulPartyRole_tab(1)":v["creator"]["role"],
                "MulDate0(1)":f"{date.today().strftime('%d-%m-%YYYY')}"
                }
        for i in range(0,len(v["supplements"])):
            tabname = f"Supplementary_tab({i+1})"
            model[tabname] = v["supplements"][i]
        models.append(model)

    with open("testcsv.csv",'w',encoding="utf-8",newline="") as f:
        headers = models[0].keys()
        writer = csv.DictWriter(f,fieldnames = headers)
        writer.writeheader()
        writer.writerows(models) 

def command_buildOne(args):
    projectname = args.projectname
    inputdir = args.inputdir
    desc = args.desc
    sketchfab = args.sketchfab
    emudict={projectname:{"supplements":[],
                          "creator":{"first":"Kea","last":"Johnston","role":"scanner"},
                          "registration":projectname,
                          "description":f"ISACM {projectname} 3D Model {desc}",
                          "sketchfab":f"{sketchfab}",
                          "multimedia":""}}
    #zip the tif files.
    if not Path(inputdir,f"{projectname}_TIF.zip").exists():
        filelist = [a for a in Path(inputdir,"TIF").iterdir() if a.is_file() and a.suffix.lower() == ".tif"]
        zipTheseFiles(filelist,inputdir,f"{projectname}_TIF")
    emudict[projectname]["supplements"].append(str(Path(inputdir,f"{projectname}_TIF.zip")))
    #zip the obj file.
    if Path(inputdir,"output").exists():
        if not Path(inputdir,f"{projectname}_OBJ.zip").exists():           
            filename = get_export_filename(projectname,Configurator.getConfig().getProperty("photogrammetry","export_as"))
            outputdir = Path(inputdir,"output")
            if outputdir.is_dir():
                for f in outputdir.iterdir():
                    if f.name == f"{filename}.obj":
                        dependencies = parseObjFiles(Path(outputdir,f.name))
                        zipTheseFiles(dependencies,inputdir,f"{projectname}_OBJ")
                        emudict[projectname]["supplements"].append(str(Path(inputdir,f"{projectname}_OBJ.zip")))
                        break
        emudict[projectname]["supplements"].append(str(Path(inputdir,f"{projectname}_OBJ.zip")))
    for j in Path(inputdir,"output").iterdir():
        if j.is_file() and j.name.endswith("_render.png"):
            emudict[projectname]["multimedia"]=str(j)
        if j.is_file() and j.name.endswith("ConeRollout.jpg"):
            emudict[projectname]["supplements"].append(str(j))

    generateEmuCSV(emudict)


if __name__=="__main__":

    parser = argparse.ArgumentParser(prog="generateEmu")
    subparsers = parser.add_subparsers(help="Sub-command help")
    buildOne = subparsers.add_parser("buildOne", help="Prepare one folder for Emu upload and generate a CSV for the one upload.")
    buildOne.add_argument("projectname",help="the name of the project and its obj files and psx files.")
    buildOne.add_argument("inputdir", help="Base directory of the project.", type=str)
    buildOne.add_argument("desc", help="Short description in quotes of the model", type=str)
    buildOne.add_argument("sketchfab", help="The address of the file on sketchfab.", type=str)
    buildOne.set_defaults(func=command_buildOne)
    args = parser.parse_args()
    if hasattr(args,"func"):

        args.func(args)
    else:
        parser.print_help()
    
