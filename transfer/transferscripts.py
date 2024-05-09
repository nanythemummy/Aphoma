import shutil
import os.path, math


def transferToNetworkDirectory(destpath, filestocopy):
    
    #transfer image files in directory to the networkdrive 
    if not os.path.exists(os.path.join(destpath)):
        os.mkdir(destpath)

    for f in filestocopy:
        print(f"Transfering {f}")
        shutil.copy(f,destpath)


    
#removes pics from a set of pictures such that the desired number in the configuration file is reached.
def pruneOrteryPics(filestocopy, orteryconfig):

    picsperrevolution=orteryconfig["pics_per_revolution"]
    desirednumbers=orteryconfig["pics_per_cam"]
    expectedfiles = len(desirednumbers)*picsperrevolution
    if(len(filestocopy)!=expectedfiles):
        print(f"Cannot prune: the expected number of files was {expectedfiles}, but there were really {len(filestocopy)} files in the folder.")
        return filestocopy
    finallist = []
    print("Pruning pics according to specifications per camera in the config.json file.")
    for i,k in enumerate(desirednumbers.keys()):
        if desirednumbers[k]==0:
            continue;
        fractiontoremove = (picsperrevolution-desirednumbers[k])/picsperrevolution
        for j in range(0,picsperrevolution):
            if (j*fractiontoremove)%1==0:
                finallist.append(filestocopy[i*picsperrevolution+j])
    return finallist

        
        

