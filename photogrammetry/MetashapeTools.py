import os
import Metashape
import argparse
import json
import ModelHelpers
from os import path

def buildBasicModel(photodir, projectname, projectdir, config):
    """Builds a model using the photos in the directory specified."""
    #Open a new document
    projectpath = os.path.join(projectdir,projectname+".psx")
    outputpath = os.path.join(projectdir,config["output_path"])
    maskpath = None
    if config["mask_path"] and os.path.exists(os.path.join(projectdir,config["mask_path"])):
        maskpath = os.path.join(projectdir,config["mask_path"])
    if not os.path.exists(outputpath):
        os.mkdir(outputpath)
    doc = Metashape.Document()
    try:
        if os.path.exists(projectpath):
            doc.open(path=projectpath)
        doc.save(path=projectpath)
        #add  a new chunk
        chunk=None
        if len(doc.chunks)==0:
            chunk = doc.addChunk()
        else:
            chunk=doc.chunks[0]
        #add the photos in the specified directory to that chunk.
        #don't add cameras if chunk already has them. If you want to build a new model, go delete the old one and rerun. 
        #Only add masks if adding new photos (for now.)
        if len(chunk.cameras)==0:
            images = os.listdir(photodir)
            for i in images:
                if os.path.splitext(i)[1] in [".jpg", ".tiff",".tif"]:
                    chunk.addPhotos(os.path.join(photodir,i))
            doc.save()
            #add masks if they exist.
            if maskpath:
                ext = config["mask_ext"]
                template = f"{maskpath}{os.sep}{{filename}}.{ext}"
                chunk.generateMasks(template,Metashape.MaskingMode.MaskingModeFile)
            chunk.matchPhotos(downscale=config["sparse_cloud_quality"],
                            generic_preselection=True,
                            reference_preselection=True,
                            reference_preselection_mode=Metashape.ReferencePreselectionMode.ReferencePreselectionSource,
                            filter_mask=(maskpath!=None),
                            mask_tiepoints=False,
                            filter_stationary_points=True,
                            tiepoint_limit=0,
                            reset_matches=False
            )
            chunk.alignCameras()
            doc.save()
        
        #build model.
        if not chunk.model:
            refineSparseCloud(doc, chunk, config)
            doc.save()
            chunk.buildDepthMaps(downscale=config["model_quality"], filter_mode = Metashape.FilterMode.MildFiltering)
            chunk.buildModel(source_data = Metashape.DataSource.DepthMapsData)
            doc.save()
        #detect markers
        if config["pallette"]:
            pallette = ModelHelpers.loadPallettes()[config["pallette"]]
            ModelHelpers.detectMarkers(chunk,pallette["type"])
            doc.save()
            if "scalebars" in pallette.keys():
                ModelHelpers.buildScalebarsFromList(chunk,pallette["scalebars"])
                doc.save()
        #build texture
        if not chunk.model.textures:
            chunk.buildUV(page_count=config["texture_count"], texture_size=config["texture_size"])
            chunk.buildTexture(texture_size=config["texture_size"], ghosting_filter=True)
        doc.save()
        print("Finished! Now exporting")
        chunk.exportModel(os.path.join(projectdir,projectname+".obj"))
        

    except Exception as e:
        raise e

    

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

def reorientModel(doc,config):
    #rotateBoundingBoxToMarkers(doc.chunks[0])
    objectAndRegionToWorldCenter(doc.chunks[0])
    resizeBoundingBox(doc.chunks[0])#for now, assume we will use a one-chunk model.
    doc.save()

def rotateBoundingBoxToMarkers(chunk):
    pass
def objectAndRegionToWorldCenter(chunk):
    assert(chunk.model)
    model = chunk.model
    vertices = model.vertices
    T = chunk.transform.matrix
    s = chunk.transform.matrix.scale()
    step = int(min(1E4, len(vertices)) / 1E4) + 1 #magic number.
    sum = Metashape.Vector([0,0,0])
    N = 0
    for i in range(0, len(vertices), step):
        sum += vertices[i].coord
        N += 1
    avg = sum / N
    chunk.region.center = avg
    M = Metashape.Matrix().Diag([s,s,s,1])
    origin = (-1) * M.mulp(chunk.region.center)
    chunk.transform.matrix  = Metashape.Matrix().Translation(origin) * (s * Metashape.Matrix().Rotation(T.rotation()))

def resizeBoundingBox(chunk):
    model = chunk.model
    if not model:
        print("Generate a model before orienting it.")
        return
    verts = sorted(model.vertices,key=(lambda e: e.coord.x))
    width = abs(verts[len(verts)-1].coord.x - verts[0].coord.x)

    verts.sort(key=(lambda e: e.coord.y))
    height = abs(verts[len(verts)-1].coord.y - verts[0].coord.y)

    verts.sort(key=(lambda e: e.coord.z))
    depth = abs(verts[len(verts)-1].coord.z - verts[0].coord.z)
    chunk.region.size=Metashape.Vector([float(width),float(height),float(depth)])



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
        reorientModel(doc,cfg["photogrammetry"])

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




    