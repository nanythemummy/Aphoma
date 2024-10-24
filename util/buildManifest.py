
import json
import time
import argparse
from os import listdir
from pathlib import *

import util

class Manifest:
    """Class that manages the manifest written to the disk by the listen and send script on the ortery computer. Adds files to an
    internal list and writes them to disk when asked."""
    def __init__(self, projectname, maskmode):
        self.sentfiles = []
        self.projectname = projectname
        self.maskmode = maskmode
        self.starttime = time.perf_counter()
        self.endtime = None
    def addFile(self, filepath):
        """Adds a file to the manifest.
        
        Parameters:
        ---------
        filepath: the full path of the file to add.
        """
        self.sentfiles.append(filepath)
    def finalize(self, outputdir):
        """Writes the manifest to disk.
        
        Parameters:
        ----------
        outputdir: the place to write the manifest file.
        returns: the path+filename that it wrote.
        """
        self.endtime = time.perf_counter()
        outputjson = {self.projectname:
                      {    "maskmode":self.maskmode,
                          "files":self.sentfiles,
                          "photo_start_time":self.starttime,
                          "photo_end_time":self.endtime}}
        filenametowrite = PurePath(outputdir,f"{self.projectname}_manifest.txt")
        with open(filenametowrite,'w',encoding='utf-8') as f:
            json.dump(outputjson,f)
        return filenametowrite
    
def generate_manifest(jobname:str,directory:str ,mode:int):
    """Generates a manifest based on a file full of folders. 
    
    Parameters:
    ----------
    jobname: the name of the project.
    directory: the directory currently containing images that will be built into a model.
    mode: maksing mode, either 0 or 1, where 0 is no masks, and 1 is masking from a file.

    returns: a dictionary which should be written to a json file.
    """
    manifest = Manifest(jobname,mode)
    files = []
    for f in listdir(directory):
        if f != 'Thumbs.db':
            manifest.addFile(f)
    manifest.finalize(directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="buildManifest")
    parser.add_argument("projectname", help="A string naming the project.")
    parser.add_argument("imagedir",help="Directory of images for which to build a manifest")
    parser.add_argument("maskingmode",choices=['0','1','2','3','4'], help="What type of masks should the manifest tell the recipient to build? 0=None, 1=From file, generate with Photoship droplet.")
    args = parser.parse_args()
    generate_manifest(args.projectname, args.imagedir, int(args.maskingmode))

