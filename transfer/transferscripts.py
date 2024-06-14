"""Scripts to be run on the computer controlling the photography rig, in order to facilitate transfer of photos to the computer
which will be running the processing operations."""

import shutil
import os.path


def transferToNetworkDirectory(destpath, filestocopy):
    """Copies files to a directory specified and if it doesn't exist, make it.

    Parameters:
    ----------
    destpath: Network directory to copy to.
    filestocopy: list of full paths of files to copy.
    """
    #transfer image files in directory to the networkdrive 
    if not os.path.exists(os.path.join(destpath)):
        os.mkdir(destpath)

    for f in filestocopy:
        print(f"Transfering {f}")
        shutil.copy(f,destpath)


    
#removes pics from a set of pictures such that the desired number in the configuration file is reached.
def pruneOrteryPics(filestocopy, orteryconfig):
    """Removes files from a list of filepaths based on the configuration specifiying how many pics are required for each ortery camera

    The Ortery takes too many pictures for photogrammetry at certain angles, like 90 degrees, where only about 3 pics are needed. The number of pictures per
    ortery camera is specified in the config.json file under ortery->pics_per_cam.
    This script takes the list of files to transfer to the network drive, and removes every Nth picture where N is the is the number of (
    pictures per revolution-the number of deisred pictures/ pictures per revolution.
    
    Parameters:
    -------------------------
    filestocopy: a list of files.
    orteryconfig: the dictionary of config.json under the key ortery
    """

    picsperrevolution=orteryconfig["pics_per_revolution"]
    desirednumbers=orteryconfig["pics_per_cam"]
    expectedfiles = len(desirednumbers)*picsperrevolution
    if len(filestocopy)!=expectedfiles:
        print(f"Cannot prune: the expected number of files was {expectedfiles}, but there were really {len(filestocopy)} files in the folder.")
        return filestocopy
    finallist = []
    print("Pruning pics according to specifications per camera in the config.json file.")
    for i,k in enumerate(desirednumbers.keys()):
        if desirednumbers[k]==0:
            continue
        fractiontoremove = (picsperrevolution-desirednumbers[k])/picsperrevolution
        for j in range(0,picsperrevolution):
            if (j*fractiontoremove)%1==0:
                finallist.append(filestocopy[i*picsperrevolution+j])
    return finallist