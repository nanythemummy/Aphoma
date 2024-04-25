import shutil
import os.path

#this script is for transfering files from the ortery computer to the network drive.
def transferToNetworkDirectory(jobname, inputdir, transferdir, prune=False):
    print(f"inputdir is: {inputdir}")
    #transfer image files in directory to the networkdrive with a subfolder called jobname.
    if not os.path.exists(transferdir):
        print(f"Invalid network directory in config.json: either {transferdir} does not exist, or you do not have permission to use it.")
        return
    destpath = os.path.join(transferdir, jobname)
    if not os.path.exists(os.path.join(transferdir,jobname)):
        os.mkdir(destpath)
    filestocopy = [f for f in os.listdir(inputdir) if f.endswith("cr2")]
    for f in filestocopy:
        shutil.copy(os.path.join(inputdir,f),destpath)

