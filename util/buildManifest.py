import argparse
import json
from os import listdir,path

import util

def generate_manifest(jobname:str,directory:str ,mode:int):
    """Generates a manifest based on a file full of folders. 
    
    Parameters:
    ----------
    jobname: the name of the project.
    directory: the directory currently containing images that will be built into a model.
    mode: maksing mode, either 0 or 1, where 0 is no masks, and 1 is masking from a file.

    returns: a dictionary which should be written to a json file.
    """
    files = []
    for f in listdir(directory):
        if f != 'Thumbs.db':
            files.append(f)
    mn = {jobname:{"maskmode":mode, "files":files}}
    return mn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="buildManifest")
    parser.add_argument("projectname", help="A string naming the project.")
    parser.add_argument("imagedir",help="Directory of images for which to build a manifest")
    parser.add_argument("maskingmode",choices=['0','1','2'], help="What type of masks should the manifest tell the recipient to build? 0=None, 1=From file, generate with Photoship droplet.")
    args = parser.parse_args()
    manifest = generate_manifest(args.projectname, args.imagedir, int(args.maskingmode))
    with open(f"{path.join(args.imagedir,args.projectname)}_manifest.txt",'w', encoding='utf-8') as doc:
        json.dump(manifest,doc)
