"""This module does a lot of metashape specific operations on the model, such as marker detection and loading the different marker palettes.
The code in MetashapeTools.py should focus on orchestration, and most number-crunching should happen here."""

import math
import Metashape
from util.util import load_palettes, TexturePageScalingCutoffs
from util.PipelineLogging import getLogger as getGlobalLogger

LOGGER = getGlobalLogger(__name__)
targetTypes = {
    "Circular":Metashape.TargetType.CircularTarget,
    "12bit":Metashape.TargetType.CircularTarget12bit,
    "14bit":Metashape.TargetType.CircularTarget14bit,
    "16bit":Metashape.TargetType.CircularTarget16bit,
    "20bit":Metashape.TargetType.CircularTarget20bit,
    "Cross":Metashape.TargetType.CrossTarget
}

def set_chunk_accuracy(chunk):

    """sets the acuracy value for the chunk. This code is derived from JP Brown's script for detecting 12 bit markers. def detect_12bit_markers.
    Parameters:
    -----------
    chunk: the Metashape.chunk with scalebars & markers.
    """
     # set accuracy values for markers and scale bars in the chunk
    chunk.tiepoint_accuracy = 0.25 # pixels WHAT ARE THESE MAGIC NUMBERS?
    chunk.marker_projection_accuracy = 0.5 # pixels
    chunk.marker_location_accuracy = Metashape.Vector( (5.0e-5, 5.0e-5, 5.0e-5) ) # meters (= 0.05 mm)

def convert_unit_to_meters(unit:str,val:float)->float:
    """Takes an input value and a unit and converts that value to meters based on unit.
    
    Parameters:
    -----------
    unit: string: either cm, mm, or km
    val: the falue to convert.
    
    returns a float of the converted value.
    """
    unit = str.lower(unit)
    if unit == "cm":
        return val*0.01
    elif unit == "mm":
        return val*0.001
    elif unit == "km":
        return val*100.0
    else:
        return val*1.0
    
def getNumberedTarget(targetnumber:int, chunk):
    name = f"target {targetnumber}"
    desiredmarker = None
    for marker in chunk.markers:
        if marker.label ==name:
            desiredmarker = marker
            break
    return desiredmarker

def getNumTexturePagesByVolume(chunk):
    
    vol = chunk.model.volume()
    if vol >= TexturePageScalingCutoffs.MED_OBJ.value:
        return 4
    elif vol >= TexturePageScalingCutoffs.SMALL_OBJ.value:
        return 2
    else: 
        return 1


def getLongestRunOfSequentialTargets(chunk):
    chunk.sortMarkers()
    markers = chunk.markers.copy()
    markers.reverse()
    prevmarker = None
    sequentialtargets = []
    groupsoftargets = []
    for marker in markers:
        if prevmarker is None:
            prevmarker = marker
            sequentialtargets.append(marker)
            continue
        marker1 = int(prevmarker.label.split(" ")[1])
        marker2 = int(marker.label.split(" ")[1])
        if abs(marker2-marker1) == 1 and \
            (sequentialtargets[0].label == prevmarker.label or are_points_colinear(sequentialtargets[0],prevmarker,marker)):
                sequentialtargets.append(marker)
        else:
            if len(sequentialtargets)>1:
                groupsoftargets.append(sequentialtargets)
            sequentialtargets = [marker]
        prevmarker = marker
    if len(groupsoftargets) == 0:
        return None, None, 0
    else:
        groupsoftargets.sort(key = lambda s:len(s))
        groupsoftargets.reverse()
        first= groupsoftargets[0][0]
        last = groupsoftargets[0][-1]
        distance = len(groupsoftargets[0])-1
        return first,last, distance

def are_points_colinear(point1,point2,point3):
    smol = 0.02
    try:
        vec1 = point2.position-point1.position
        vec2 = point3.position-point1.position
        det = Metashape.Vector.cross(vec2,vec1)
        #don't expect it to be exactly zero because of calculation errors. expect it to be close.
        lengdet = math.sqrt(det.x**2+det.y**2+det.z**2)
        return abs(lengdet) < smol
    except AttributeError:
        return False #Turns out points can have no position. who would have thought it.
    
def build_scalebars_from_sequential_targets(chunk, scalebardefinitions):
    """Takes scalebar definition info and builds scalebars from it based the label numbers being sequential..
    
    Parameters:
    ---------------
    chunk: The Metashape Chunk with the scalebars.
    scalebardefinitions: a list of small dictionaries of the format:    "scalebars":{
                "type":"sequential",
                "labelinterval":1,
                "distance":2.0,
                "units":"cm"
            },
                 These can be found in markerpalettes.json
    """
    marker1,marker2, dist = getLongestRunOfSequentialTargets(chunk)
    if dist == 0:
        print("Not enough markers to properly scale.")
        return # if there weren't enough markers to calculate this, return.
    units = scalebardefinitions["units"]
    distance = scalebardefinitions["distance"]
    scalebar = None
    for existingbar in chunk.scalebars:
        if (existingbar.point0==marker1 or existingbar.point0==marker1) and (existingbar.point0==marker2 or existingbar.point1==marker2):
            scalebar = existingbar
            break
    if scalebar is None:
        scalebar = chunk.addScalebar(marker1,marker2)
    scalebar.reference.distance = convert_unit_to_meters(units,distance*dist)
    scalebar.reference.accuracy = 1.0e-5
    scalebar.reference.enabled = True
    chunk.updateTransform()

def build_scalebars_from_list(chunk,scalebardefinitions):
    """Takes a list of marker pairs forming scalebars with the associated distances, finds those markers in the agisoft chunk,
    and creates scalebars based on them.
    
    Parameters:
    ---------------
    chunk: The Metashape Chunk with the scalebars.
    scalebardefinitions: a list of small dictionaries of the format: {
                "points":[pt1,pt2],
                "distance":x,
                "units":"cm"
                },
                 These can be found in markerpalettes.json
    """
    set_chunk_accuracy(chunk)
    for definition in scalebardefinitions:
        marker1 = getNumberedTarget(definition['points'][0], chunk)
        marker2 = getNumberedTarget(definition['points'][1], chunk)
        if marker1 and marker2:
            #either make a new scalebar or find one that already exists between the two markers and reset the distance between them.
            scalebar = None
            for existingbar in chunk.scalebars:
                if (existingbar.point0==marker1 or existingbar.point0==marker1) and (existingbar.point0==marker2 or existingbar.point1==marker2):
                    scalebar = existingbar
                    break
            if scalebar is None:
                scalebar = chunk.addScalebar(marker1,marker2)
            scalebar.reference.distance = convert_unit_to_meters(definition["units"],definition["distance"])
            scalebar.reference.accuracy = 1.0e-5
            scalebar.reference.enabled = True
    chunk.updateTransform()

def close_holes(chunk):
  """Closes any holes in the model.
    
    Parameters:
    ---------------
    Chunk: the metashape chunk we want to act on.
    """
  if chunk.model:
      threshold = 100
      chunk.model.closeHoles(level = threshold)\
      
def set_region_to_local_coordinates(chunk):
    """Cribbed this from here because I am still pretty iffy on how metashape's coordinate systems work: https://github.com/agisoft-llc/metashape-scripts"""
    trans = chunk.transform.matrix
    transformvect = trans.mulp(Metashape.Vector([0,0,0]))
    mat = Metashape.Matrix().Diag([1,1,1,1])
    if chunk.crs:
        mat = chunk.crs.localframe(transformvect)
    mat = mat*trans
    scale = math.sqrt(mat[0,0]**2 + mat[0,1]**2 + mat[0,2]**2) #OMG WHY IS IT GETTING THE DISTANCE OF THE TOP ROW OF THIS MATRIX?! Why these numbers?
    rotation = Metashape.Matrix([[mat[0, 0], mat[0, 1], mat[0, 2]],
                                [mat[1, 0], mat[1, 1], mat[1, 2]],
                                [mat[2, 0], mat[2, 1], mat[2, 2]]])
    rotation*=(1./scale)
    reg = chunk.region
    reg.rot = rotation.t()
    chunk.region = reg

def resize_bounding_box(chunk, percentx=100.0,percenty=100.0,percentz=25.0,negativedirection = True):
    set_region_to_local_coordinates(chunk)
    cloud_dim = get_model_dimensions(chunk)
    dimx= abs(cloud_dim["max_x"]-cloud_dim["min_x"])
    dimy= abs(cloud_dim["max_y"]-cloud_dim["min_y"])
    dimz= abs(cloud_dim["max_z"]-cloud_dim["min_z"])
    dimxm = dimx*(percentx/100.0)
    dimym = dimy*(percenty/100.0)
    dimzm = dimz*(percentz/100.0)
    print(f"dimx {dimx}, dimy {dimy}, dimz {dimz}")
    chunk.region.size = Metashape.Vector([dimxm,dimym,dimzm])
    if not negativedirection:
        chunk.region.center = Metashape.Vector([cloud_dim["min_x"]+dimxm/2.0,
                                                cloud_dim["min_y"]+dimym/2.0,
                                                cloud_dim["min_z"]+dimzm/2.0])
    else:
        chunk.region.center = Metashape.Vector([cloud_dim["max_x"]-dimxm/2.0,
                                        cloud_dim["max_y"]-dimym/2.0,
                                        cloud_dim["max_z"]-dimzm/2.0])

def get_model_dimensions(chunk):
    if chunk.model:
        pts = chunk.model.vertices
        verts = []
        l = len(pts)
        for p in range(0,l):
            verts.append(pts[p].coord)
        maxmin = {}
        xs = sorted(verts,key=lambda pt: pt[0])
        maxmin["max_x"] = xs[len(xs)-1][0]
        maxmin["min_x"] = xs[0][0]
        ys = sorted(verts, key=lambda pt:pt[1])
        maxmin["max_y"] = ys[len(ys)-1][1]
        maxmin["min_y"] = ys[0][1]
        zs = sorted(verts, key=lambda pt:pt[2])
        maxmin["max_z"] = zs[len(zs)-1][2]
        maxmin["min_z"] = zs[0][2]
        return maxmin

def cleanup_blobs(chunk):
    """Cleans up freestanding floating geometry leaving the largest object behind.
    
    Parameters:
    ---------------
    Chunk: the metashape chunk we want to act on.
    """
    if chunk.model:
        stats = chunk.model.statistics()
        while stats.components>1:
            #when there are a lot of blobs, assume that the largest one is the one we want to keep. We don't have a list of the blobs, but we do know how many there are.
            #so, take the average and keep filtering until there is one left, and that will be the largest.
            faceave = math.ceil(stats.faces/stats.components)
            stats = removeComponentsUnderFaceThreshold(chunk,faceave)
        removeComponentsUnderFaceThreshold(chunk,0)

def removeComponentsUnderFaceThreshold(chunk,threshold):
    chunk.model.removeComponents(threshold)
    return chunk.model.statistics()
    
def detect_markers(chunk, markertype:str):
    """Given a metashape chunk, detect the markers that occur in that chunk. These will be stored by metashape under chunk->markers
    Parameters:
    --------------
    chunk: the metashape chunk with the markers in it.
    type: the type of marker to detect. Mappings of strings to metashape types are given in the targetTypes variable above.
    """

    set_chunk_accuracy(chunk)
    # remove any existing markers from this chunk
    if len(chunk.markers):
        chunk.remove(chunk.markers)

    print("Detecting and assigning 12-bit targets")
    # detect markers using defaults (12-bit markers, tolerance: 50, filter_mask: False, etc.)
    chunk.detectMarkers(target_type=targetTypes[markertype], filter_mask=False) 

    # bail if we have no markers
    if len(chunk.markers) ==  0:
        print("- no markers detected")
    else:
        print(f"- found {len(chunk.markers)} markers")
    # update markers
    chunk.refineMarkers()

def optimize_cameras(chunk, final_optimization=False):
    """Runs the optimize cameras function in metashape.
    
    Parameters:
    ----------------
    chunk: the chunk with the cameras to optimize.
    final_optimization: A different set of camera parameters are used the final time this is called in the error reduction cycle. 
    Pass in true if you would like that.
    """
    
    #runs the optimize camera function, setting a handfull of the statistical fitting options to true only if the parameter is true,
    #which ought to occur on the final iteration of a process.
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

def refine_sparse_cloud(doc,chunk,error_thresholds:dict):
    """Performs the error reduction/optimization algorithm as described by Neffra Matthews and Noble,Tommy. "In the Round Tutorial", 2018. 
    
    Parameters:
    ---------------
    doc: The metashape document...this is so we can save between various stages.
    chunk: the chunk on which we are currently operating.
    config: the config.json subdictionary under the key "photogrammetry"

    """
    LOGGER.info("Refining sparse cloud on chunk %s", chunk)
    #copied from the script RefineSparseCloud.py     
    optimize_cameras(chunk,False)
    doc.save()
    #get number of points before refinement:
    
    #Remove points with reconstruction uncertainty error above threshold.
    remove_above_error_threshold(chunk,
                              Metashape.TiePoints.Filter.ReconstructionUncertainty,
                              error_thresholds["reconstruction_uncertainty"],
                              error_thresholds["reconstruction_uncertainty_max_selection"])
    optimize_cameras(chunk,False)
    doc.save()
    #Remove points with a projection accuracy error aabove threshold.
    remove_above_error_threshold(chunk,
                            Metashape.TiePoints.Filter.ProjectionAccuracy,
                            error_thresholds["projection_accuracy"],
                            error_thresholds["projection_accuracy_max_selection"])
    optimize_cameras(chunk,False)
    doc.save()
    #remove points with a reprojection error of above threshold, only removing a set percentage of overall points at a time.
    num_points = len(chunk.tie_points.points)
    min_remaining_points = num_points-num_points*error_thresholds["reprojection_max_selection"]
    reachedgoal = False
    while num_points > min_remaining_points and not reachedgoal:
        reachedgoal = remove_above_error_threshold(chunk,
                                    Metashape.TiePoints.Filter.ReprojectionError,
                                    error_thresholds["reprojection_error"],
                                    error_thresholds["reprojection_max_selection_per_iteration"])
        optimize_cameras(chunk,False)
        num_points = len(chunk.tie_points.points)
    optimize_cameras(chunk,True)
    doc.save()

def remove_above_error_threshold(chunk, filtertype,max_error,max_points):
    """ This attempts to select and remove all points above a given error threshold in max_error, up to a maximum percentage of acceptable points to remove, max_points. 
    It returns true if it succeeds in removing all points with error higher than the threshold without first reaching the maximum selection.
   
     Parameters:
    -------------------------
    chunk: the chunk on which we are operating.
    filtertype: the filtertype in the Metashape.TiePoints.Filter enumeration.
    max_error: the max error value for the filter type as specified in config.json.
    max_points: the max amount of points that should be selected at a time to reduce error, as specified in config.json.
    
    returns true or false depending on whether the max error was reached without first reaching the maximum points selected.
    """
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

def find_axes_from_markers_in_plane(chunk,palette:str):
    if not chunk.markers:
        LOGGER.info("No markers to align on chunk %s.",chunk.name)
        return []
    if not palette.get("plane",0) or not palette.get("xaxis",0):
        LOGGER.warning("Can't find the markers in a plane if there is no plane specified in the marker palette.")
        return []
    plane,xaxis = [[] for _ in range(2)]
    markers = chunk.markers

    for m in markers:
        if not m.position is None:
            lookfor = (int)(m.label.split()[1])
            if lookfor in palette["plane"]:
                plane.append({"name":m.label,"pos":lookfor.position})
                if lookfor in palette["xaxis"]:
                    xaxis.append({"name":m.label,"id":m.id,"pos":m.position})
    if len(xaxis)>=1 and len(plane)>2:
        #Wooooo we can calculate this.
        LOGGER.info("Calculating plane from %s, %s, %s",plane[0]["name"],plane[1]["name"],plane[2]["name"])
        veca = plane[0]["position"]-plane[1]["position"]
        vecb = plane[0]["position"]-plane[2]["position"]
        y_axis = Metashape.Vector.cross(veca,vecb)
        y_axis.normalize()
        LOGGER.info("Y-axis is %s."%y_axis)
        x_axis = Metashape.Vector(xaxis[0]["position"]).normalize()
        LOGGER.info("X-axis is %s."%x_axis)
        z_axis  = Metashape.vector.cross(x_axis,y_axis)
        z_axis.normalize()
        LOGGER.info("Z-axis is %s."%z_axis)
        return[x_axis,y_axis,z_axis]

    else:
        LOGGER.error("Not enough markers to orient model." )
        return []
            



    
def find_axes_from_markers(chunk,palette:str):
    """Given a chunk with a model on it, and detected markers, use the palette definiton to try to figure out the x, y and z axes.
    
    Parameters:
    -------------
    chunk: the chunk on which we are operating.
    pallette: tha name of the palette we are using for this model. Get it from config.json.

    returns: a list of unit vectors corresponding to x,y, and z axes.
    """
    if not chunk.markers:
        LOGGER.info("No markers to align on chunk %s."%chunk.name)
        return []
    xaxis = []
    zaxis = []
    markers = chunk.markers
    markers.reverse() #generally higher numbers are on the inside, so search from inside out.
    for m in markers:
        if not m.position==None:
            lookforlabel = (int)(m.label.split()[1]) #get the number of the label to look for it in the list of axes.
            if lookforlabel in palette["axes"]["xpos"] or lookforlabel in palette["axes"]["xneg"]:
                xaxis.append(m.position)
            if lookforlabel in palette["axes"]["zpos"] or lookforlabel in palette["axes"]["zneg"]:
                zaxis.append(m.position)
            if len(xaxis)>=2 and len(zaxis)>=2:
                break
    if len(xaxis)<2 or len(zaxis) <2:
        print("Not enough data to determine x and z axes.")
        return []
    ux = (xaxis[1]-xaxis[0])
    uz = (zaxis[1]-zaxis[0])
    yaxis = Metashape.Vector.cross(uz,ux)
    ux.normalize()
    uz.normalize()
    yaxis.normalize()
    return [ux,yaxis,uz]

def move_model_to_world_origin(chunk):
    
    """Uses the center of the bounding box as a substitute for the center of the model, and translates the model to world zero based
    on that transform.

    Parameters:
    -----------------
    chunk: the chunk on which we are operating.
    
    """
    chunk.resetRegion()
    regioncenter = chunk.region.center
    height = chunk.region.size.y
    print(chunk.region.size)


    newtranslation = Metashape.Matrix([[1,0,0,regioncenter[0]],
                                    [0,1,0,regioncenter[1]],
                                    [0,0,1,regioncenter[2]],
                                    [0,0,0,1]])
    chunk.transform.matrix *=newtranslation.inv()
    print(f"moving to zero, inshallah.: {chunk.transform.matrix}")
    chunk.resetRegion()

def align_markers_to_axes(chunk,axes): 
    """Takes the local coordinates y axis of the model as calculated from a marker pallette and aligns it with world Y axis in metashape.
    
    Parameters:
    chunk: the chunk on which we are operating
    axes: a list of metashape vectors in the order x,y,z.
    """
    transmat = chunk.transform.matrix
    scale = math.sqrt(transmat[0,0]**2+transmat[0,1]**2 + transmat[0,2]**2) #length of the top row in the matrix, but why?
    scale*=1000.0 #by default agisoft assumes we are using meters while we are measuring in mm in meshlab and gigamesh.
    scalematrix = Metashape.Matrix().Diag([scale,scale,scale,1])
    newaxes = Metashape.Matrix([[axes[0].x,axes[0].y, axes[0].z,0],
                   [axes[1].x,axes[1].y,axes[1].z,0],
                   [axes[2].x, axes[2].y,axes[2].z,0],
                   [0,0,0,1]])

    chunk.transform.matrix=scalematrix*newaxes 
