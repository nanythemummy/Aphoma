import os
import Metashape
import argparse
import json
import ModelHelpers
import traceback
import math
from os import path

def buildBasicModel(photodir, projectname, projectdir, config, decimate = True):
    """Builds a model using the photos in the directory specified."""
    #Open a new document
    projectpath = os.path.join(projectdir,projectname+".psx")
    outputpath = os.path.join(projectdir,config["output_path"])
    maskpath = None
    if "mask_path" in config.keys() and os.path.exists(os.path.join(projectdir,config["mask_path"])):
        maskpath = os.path.join(projectdir,config["mask_path"])
    if not os.path.exists(outputpath):
        os.mkdir(outputpath)
    doc = Metashape.Document()
    try:
        if os.path.exists(projectpath):
            doc.open(path=projectpath)
        doc.save(path=projectpath)
        #add  a new chunk
        current_chunk=None
        if len(doc.chunks)==0:
            current_chunk = doc.addChunk()
            current_chunk.label=projectname
        else:
            current_chunk=doc.chunks[0]
        #add the photos in the specified directory to that chunk.
        #don't add cameras if chunk already has them. If you want to build a new model, go delete the old one and rerun. 
        #Only add masks if adding new photos (for now.)
        if len(current_chunk.cameras)==0:
            images = os.listdir(photodir)
            for i in images:
                if os.path.splitext(i)[1] in [".jpg", ".tiff",".tif"]:
                    current_chunk.addPhotos(os.path.join(photodir,i))
            doc.save()
            #add masks if they exist.
            if maskpath:
                ext = config["mask_ext"]
                template = f"{maskpath}{os.sep}{{filename}}.{ext}"
                current_chunk.generateMasks(template,Metashape.MaskingMode.MaskingModeFile)
            current_chunk.matchPhotos(downscale=config["sparse_cloud_quality"],
                            generic_preselection=True,
                            reference_preselection=True,
                            reference_preselection_mode=Metashape.ReferencePreselectionMode.ReferencePreselectionSource,
                            filter_mask=(maskpath!=None),
                            mask_tiepoints=False,
                            filter_stationary_points=True,
                            tiepoint_limit=0,
                            reset_matches=False
            )
            current_chunk.alignCameras()
            doc.save()
        #build model.
        if not current_chunk.model:
            refineSparseCloud(doc, current_chunk, config)
            doc.save()
            current_chunk.buildDepthMaps(downscale=config["model_quality"], filter_mode = Metashape.FilterMode.MildFiltering)
            current_chunk.buildModel(source_data = Metashape.DataSource.DepthMapsData)
            doc.save()
        #detect markers
        if "pallette" in config.keys():
            pallette = ModelHelpers.loadPallettes()[config["pallette"]]
            if not current_chunk.markers:
                ModelHelpers.detectMarkers(current_chunk,pallette["type"])
                doc.save()
            if "scalebars" in pallette.keys() and not current_chunk.scalebars:
                ModelHelpers.buildScalebarsFromList(current_chunk,pallette["scalebars"])
                doc.save()         
        #build texture
        if decimate and len(doc.chunks)<2:
            newchunk = current_chunk.copy(items=[Metashape.DataSource.DepthMapsData, Metashape.DataSource.ModelData], keypoints=True)
            newchunk.label = f"{current_chunk.label} lowpoly 50K"
            newchunk.decimateModel(replace_asset=True,face_count=50000)
        for c in doc.chunks:
            if not c.model.textures:
                c.buildUV(page_count=config["texture_count"], texture_size=config["texture_size"])
                c.buildTexture(texture_size=config["texture_size"], ghosting_filter=True)
                doc.save()
            reorientModel(c,config)
            doc.save()
            print(f"Finished! Now exporting chunk {c.label}")
            labelname = c.label.replace(" ","")
            ext = config["export_as"]
            c.exportModel(path=f"{os.path.join(projectdir,labelname)}_{ext.upper()}.{ext}",
                        texture_format = Metashape.ImageFormat.ImageFormatPNG,
                        embed_texture=(ext=="ply") )
    except Exception as e:
        print(e)
        print(traceback.format_exc)

#runs the optimize camera function, setting a handfull of the statistical fitting options to true only if the parameter is true,
#which ought to occur on the final iteration of a process.
def optimizeCameras(chunk, final_optimization=False):
    chunk.optimizeCameras(fit_f=True,
                          fit_cx=True,
                          fit_cy=True,
                          fit_b1=final_optimization,
                          fit_b2=final_optimization,
                          fit_k1=True,
                          fit_k2=True,
                          fit_k3=True,
                          fit_k4=final_optimization,
                          fit_p1 = True,
                          fit_p2=True,
                          fit_p3=final_optimization,
                          adaptive_fitting=False,
                          tiepoint_covariance=False)

#Performs the error reduction/optimization algorithm as described by Neffra Matthews and Noble,Tommy. "In the Round Tutorial", 2018. 
def refineSparseCloud(doc,chunk,config):
    #copied from the script RefineSparseCloud.py     
    chunk.optimizeCameras()
    doc.save()
    #get number of points before refinement:
    
    #Remove points with reconstruction uncertainty error above threshold.
    error_thresholds = config["error_thresholds"]
    removeAboveErrorThreshold(chunk,
                              Metashape.TiePoints.Filter.ReconstructionUncertainty,
                              error_thresholds["reconstruction_uncertainty"],
                              error_thresholds["reconstruction_uncertainty_max_selection"])
    chunk.optimizeCameras()
    doc.save()
    #Remove points with a projection accuracy error aabove threshold.
    removeAboveErrorThreshold(chunk,
                            Metashape.TiePoints.Filter.ProjectionAccuracy,
                            error_thresholds["projection_accuracy"],
                            error_thresholds["projection_accuracy_max_selection"])
    chunk.optimizeCameras()
    doc.save()
    #remove points with a reprojection error of above threshold, only removing a set percentage of overall points at a time.
    num_points = len(chunk.tie_points.points)
    min_remaining_points = num_points-num_points*error_thresholds["reprojection_max_selection"]
    reachedgoal = False
    while num_points > min_remaining_points and not reachedgoal:
        reachedgoal = removeAboveErrorThreshold(chunk,
                                    Metashape.TiePoints.Filter.ReprojectionError,
                                    error_thresholds["reprojection_error"],
                                    error_thresholds["reprojection_max_selection_per_iteration"])
        chunk.optimizeCameras()
        num_points = len(chunk.tie_points.points)
    chunk.optimizeCameras(True)
    doc.save()

    
# attempts to select and remove all points above a given error threshold in max_error, up to a maximum percentage of acceptable points to remove, max_points.
# returns true if it succeeds in removing all points with error higher than the threshold without first reaching the maximum selection.
def removeAboveErrorThreshold(chunk, filtertype,max_error,max_points):
    removed_above_threshold=False
    tiepoints = chunk.tie_points
    num_points = len(tiepoints.points)
    max_removal = num_points*max_points
    print(f"Selecting and attempting to remove points with error {filtertype} above {max_error} with a max removal of {max_removal} of {num_points}.")
    errorfilter = Metashape.TiePoints.Filter()
    errorfilter.init(tiepoints,filtertype)
    errorvals = errorfilter.values.copy()
    errorvals.sort(reverse=True)
    for i,v in enumerate(errorvals):
        if v > max_error and  (i+1) <= max_removal:
            continue
        else:
            errorfilter.selectPoints(v)
            tiepoints.removeSelectedPoints()
            removed_above_threshold=(v<=max_error)
            break
    return removed_above_threshold

def reorientModel(chunk,config):
    axes = findAxesFromMarkers(chunk,config)
    #AlignMarkersToAxes(chunk,axes)


def findAxesFromMarkers(chunk,config):
    pallette = ModelHelpers.loadPallettes()[config["pallette"]]
    if not chunk.markers:
        print("No marker pallette defined or markers detected. Cannot detect orientation from pallette.")
        return
    xaxis = []
    zaxis = []
    for m in chunk.markers:
        lookforlabel = (int)(m.label.split()[1]) #get the number of the label to look for it in the list of axes.
        if lookforlabel in pallette["axes"]["xpos"] or lookforlabel in pallette["axes"]["xneg"]:
            xaxis.append(m.position)
        elif lookforlabel in pallette["axes"]["zpos"] or lookforlabel in pallette["axes"]["zneg"]:
            zaxis.append(m.position)
        if len(xaxis)>=2 and len(zaxis)>=2:
            break
    ux = (xaxis[1]-xaxis[0])
    uz = (zaxis[1]-zaxis[0])
    yaxis = Metashape.Vector.cross(ux,uz)
    ux.normalize()
    uz.normalize()
    yaxis.normalize()
    return [ux,yaxis,uz]

def AlignMarkersToAxes(chunk,axes): #takes a vector and aligns it with the y axis. fully expect to rewrite this as I get better at the math.
    transmat = chunk.transform.matrix
    regioncenter = chunk.region.center
    scale = math.sqrt(transmat[0,0]**2+transmat[0,1]**2 + transmat[0,2]**2) #length of the top row in the matrix, but why?
    scale*=1000.0 #by default agisoft assumes we are using meters while we are measuring in mm in meshlab and gigamesh.
    scalematrix = Metashape.Matrix().Diag([scale,scale,scale,1])
    newaxes = Metashape.Matrix([[axes[0].x,axes[0].y, axes[0].z,0],
                   [axes[1].x,axes[1].y,axes[1].z,0],
                   [axes[2].x, axes[2].y,axes[2].z,0],
                   [0,0,0,1]])
    newtranslation = Metashape.Matrix([[1,0,0,regioncenter[0]],
                                       [0,1,0,regioncenter[1]],
                                       [0,0,1,regioncenter[2]],
                                       [0,0,0,1]])
    chunk.transform.matrix=scalematrix*newaxes
    print(f"resetting axes: {chunk.transform.matrix}")
    chunk.transform.matrix *=newtranslation.inv()
    print(f"moving to zero, inshallah.: {chunk.transform.matrix}")
    chunk.resetRegion()


if __name__=="__main__":
    def loadConfigFile(configpath):
        cfg = {}
        with open(path.abspath(args.config)) as f:
            cfg = json.load(f)
        return cfg["config"]
    def commandBuildModel(args):
        cfg = loadConfigFile(args.config)
        buildBasicModel(args.photos,args.jobname,args.outputdirectory,cfg["photogrammetry"])
    
    def orientModel(args):
        cfg = loadConfigFile(args.config)
        doc = Metashape.Document()
        if os.path.exists(args.psxpath):
            doc.open(path=args.psxpath)
        reorientModel(doc.chunks[0],cfg["photogrammetry"])

    parser = argparse.ArgumentParser(prog="MetashapeTools")
    subparsers = parser.add_subparsers(help="Sub-command help")
    
    buildparser = subparsers.add_parser("build", help="Build the model in the given psx file.")
    orientparser = subparsers.add_parser("orient", help="Orients a model on origin, and rotates it into position if markers are present.")

    buildparser.add_argument("jobname", help="The name of the project")
    buildparser.add_argument("photos", help="Place where the photos in tiff or jpeg format are stored.")
    buildparser.add_argument("outputdirectory", help="Where the intermediary files for building the model and the ultimate model will be stored.")
    buildparser.add_argument("config", help="The location of config.json")
    buildparser.set_defaults(func=commandBuildModel)

    orientparser.add_argument("psxpath", help="psx file to load")
    orientparser.add_argument("config", help="The location of config.json")
    orientparser.set_defaults(func=orientModel)

    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()




    