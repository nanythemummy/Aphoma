import shutil
import os.path

#this script is for transfering files from the ortery computer to the network drive.
def transferToNetworkDirectory(jobname, filestocopy, transferdir, prune=False):
    
    #transfer image files in directory to the networkdrive with a subfolder called jobname.
    if not os.path.exists(transferdir):
        print(f"Invalid network directory in config.json: either {transferdir} does not exist, or you do not have permission to use it.")
        return
    destpath = os.path.join(transferdir, jobname)
    if not os.path.exists(os.path.join(transferdir,jobname)):
        os.mkdir(destpath)

    for f in filestocopy:
        shutil.copy(f,destpath)

def pruneOrteryPics(filestocopy, orteryconfig):
    picsperrevolution=orteryconfig["pics_per_revolution"]
    desirednumbers=orteryconfig["pics_per_cam"]
    expectedfiles = len(desirednumbers)*picsperrevolution
    filestocopy.sort()
    if(len(filestocopy)!=expectedfiles):
        print(f"Cannot prune: the expected number of files was {expectedfiles}, but there were really {len(filestocopy)} files in the folder.")
        return filestocopy
    print(filestocopy)
