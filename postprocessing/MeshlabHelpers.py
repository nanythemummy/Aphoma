import argparse
import pymeshlab
from pathlib import Path
import os
import subprocess
import json

def execute_blender_script(scriptname:str, args:dict,config):
    """Executes the named blender script and using the blender executable
    specified in the same place.

    Parameters:
    ------------------------
    scriptname = absolute path to a python script that can be run from within blender.
    args: a dictionary of arguments in the form key:value"""
    
    params = "-- "
    for k,v in args.items():
        params += f" --{k}=\"{v}\""

    bexec = os.path.join(config["postprocessing"]["blender_exec"])
    cmd = f"\"{bexec}\" --background --factory-startup --python \"{scriptname}\" {params}"
    print(cmd)

    subprocess.run(cmd,shell=True,check = False)

def bottom_to_origin(filename,outputname):
    """Takes a mesh in the format obj, ply, or other meshlab supported formats and translates the local origin to 0,0,0, then
    offsets the model by half the height of the bounding box so that the base of the model is on the origin.
    
    Parameters:
    --------------------
    filename: The path of the file to be input.
    outputname: the full path of the file you want written out."""
    
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(filename)
    ms.compute_matrix_from_translation(traslmethod ='Center on Layer BBox')
    yval = ms.current_mesh().bounding_box().dim_y()
    ms.compute_matrix_from_translation(traslmethod="XYZ translation",axisx=0.0,axisy=yval/2.0, axisz=0.0)
    ms.save_current_mesh(outputname)

def command_snapshot(args,config):
    
    scriptdir = config["postprocessing"]["script_directory"]
    scriptname = "snapshot_with_scale.py"
    script = os.path.join(os.path.join(scriptdir),scriptname)
    print(f"Executing Blender Script {script}")
    params = {"input":args.inputdir,"render":os.path.dirname(args.inputdir),"scale":config["postprocessing"]["scale_path"], "flipx":args.flip}
    execute_blender_script(script,params,config)

def command_bto(args,config):

    if os.path.isfile(args.inputdir) and os.path.isdir(os.path.dirname(args.outputdir)):
        bottom_to_origin(args.inputdir,args.outputdir)
    else:
        print("Path: {args.inputdir} is not a valid file or {args.outputdir} is not a real directory.")

if __name__=="__main__":
    
    parser = argparse.ArgumentParser(prog="meshlabScripts")
    subparsers = parser.add_subparsers(help="Sub-command help")
    translateprocessor = subparsers.add_parser("bottomToOrigin", help="Translate the object so that the bottom of it is on 0,0, assuming it's centered on the origin.")
    translateprocessor.add_argument("inputdir", help="Directory of raw files to operate on.", type=str)
    translateprocessor.add_argument("outputdir", help="Directory to put the output processed files.", type=str)
    translateprocessor.set_defaults(func=command_bto)
    snapshot = subparsers.add_parser("snapshot", help="Uses blender to build a scene with the object and a scale and to take a snapshot of it.")
    snapshot.add_argument("inputdir", help="Directory of the ply file to operate on.", type=str)
    snapshot.add_argument("--flip", help="Directory of the ply file to operate on.", action="store_true")
    snapshot.set_defaults(func=command_snapshot)
    args = parser.parse_args()
    if hasattr(args,"func"):
        parentpath = Path(__file__).parent.parent.absolute()
        with open(Path(parentpath,"config.json"),'r') as f:
            config = json.load(f)["config"]
        args.func(args,config)
    else:
        parser.print_help()
    
