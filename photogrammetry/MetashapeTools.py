import os
import Metashape

def build_basic_model(photodir, outputdir, projectname, config):
    """Builds a model using the photos in the directory specified."""
    #Open a new document
    projectpath = os.path.join(outputdir,projectname+".psx")
    doc = Metashape.Document()
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
    images = os.listdir(photodir)
    for i in images:
        if os.path.splitext(i)[1] in [".jpg", ".tiff",".tif"]:
            chunk.addPhotos(os.path.join(photodir,i))
    doc.save()
    #add masks if they exist.
    maskKeypoints=False
    if config["mask_path"]:
        mp = os.path.join(config["mask_path"])
        ext = config["mask_ext"]
        template = f"{mp}{os.sep}{{filename}}.{ext}"
        chunk.generateMasks(template,Metashape.MaskingMode.MaskingModeFile)
        maskKeypoints=True
    chunk.matchPhotos(downscale=0,
                      generic_preselection=True,
                      reference_preselection=True,
                      reference_preselection_mode=Metashape.ReferencePreselectionMode.ReferencePreselectionSource,
                      filter_mask=maskKeypoints,
                      mask_tiepoints=False,
                      filter_stationary_points=True,
                      tiepoint_limit=0,
                      reset_matches=True
    )
    chunk.alignCameras()
    doc.save()
    refineSparseCloud(doc, chunk, config)
    

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
                          fit_p3=final_optimization,
                          adaptive_fitting=False,
                          tiepoint_covariance=False)

#Performs the 
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
                            error_thresholds["project_accuracy_max_selection"])
    chunk.optimizeCameras()
    doc.save()
    #remove points with a reprojection error of above threshold, only removing a set percentage of overall points at a time.
    num_points = len(chunk.tie_points)
    min_remaining_points = num_points-num_points*error_thresholds["reprojection_max_selection"]
    reachedgoal = False
    while num_points > min_remaining_points and not reachedgoal:
        reachedgoal = removeAboveErrorThreshold(chunk,
                                    Metashape.TiePoints.Filter.ReprojectionError,
                                    error_thresholds["reprojection_error"],
                                    error_thresholds["reprojection_max_selection_per_iteration"])
        chunk.optimizeCameras()
        num_points = len(chunk.tie_points)
    chunk.optimizeCameras(True)
    doc.Save()
            
    
# attempts to select and remove all points above a given error threshold in max_error, up to a maximum percentage of acceptable points to remove, max_points.
# returns true if it succeeds in removing all points with error higher than the threshold without first reaching the maximum selection.
def removeAboveErrorThreshold(chunk, filtertype,max_error,max_points):
    removed_above_threshold=False
    points = chunk.tie_points
    num_points = len(points)
    max_removal = num_points*max_points
    print(f"Selecting and attempting to remove points with error {filtertype} above {max_error} with a max removal of {max_removal} of {num_points}.")
    errorfilter = Metashape.TiePoints.Filter()
    errorfilter.init(points,filtertype)
    errorvals = errorfilter.values.sort(reverse=True)
    for i,v in errorvals.items():
        if v > max_error and  (i+1) <= max_removal:
            continue
        else:
            errorfilter.selectPoints(v)
            points.removeSelectedPoints()
            removed_above_threshold=(v<=max_error)
    return removed_above_threshold





    