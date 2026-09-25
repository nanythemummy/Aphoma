
from pathlib import Path
import math
import itertools
from os import mkdir
import shutil
import re
import Metashape
import cv2
from util.InstrumentationStatistics import *

from util.ErrorCodeConsts import ErrorCodes
from util.PipelineLogging import getLogger as getGlobalLogger
from util.Configurator import Configurator
from util.MetashapeFileHandleSingleton import MetashapeFileSingleton
from util import util
from photogrammetry import ModelHelpers
from tasks.MetashapeTasks import MetashapeTask, MetashapeTask_DetectMarkers

# This file contains metashape tasks that are unusual, one-off, or special. Tasks in it can be experimental.
# They do things that are outside of the normal model building workflow. Eventually, if tasks from here improve on the general
# functionality of the original, they may be ported over to the main metashape tasks file.



def checkMarkerLabelExists(chunk, labelname):
    for m in chunk.markers:
        if m.label ==labelname:
            return m
    return None
def copyMarkersFromChunkToOtherChunk(chunk1,chunk2):
    #The parameters are chunk1: The chunk you are copying the markers from, and chunk2: the chunk you are copying the markers to.
    print(f"copying markers from {chunk1.label} to {chunk2.label}")
    pat = re.compile(r"\S+?([0-9]+)$")
    photostomarkers={}
    if len(chunk1.markers)>0:
        for m in chunk1.markers:
            for camera in chunk1.cameras:
                if camera in m.projections.keys():
                    projection = m.projections[camera]
                    x = projection.coord.x
                    y = projection.coord.y
                    mat = pat.match(Path(camera.photo.path).stem)
                    if mat is not None:
                        photonumber = mat.group(1)
                        if  photonumber not in photostomarkers.keys():
                            photostomarkers[photonumber] = []
                        photostomarkers[photonumber].append({"name":m.label,"x":x,"y":y })
        print(photostomarkers)
        for cam in chunk2.cameras:
            camname=Path(cam.photo.path).stem
            mat = pat.match(camname)
            if mat is not None:
                camnum = mat.group(1)
                if camnum in photostomarkers.keys():
                    newmarkers = photostomarkers[camnum]
                    for marker in newmarkers:
                        mk = checkMarkerLabelExists(chunk2,marker["name"]) or chunk2.addMarker()
                        mk.label= marker["name"]
                        mk.projections[cam]=Metashape.Marker.Projection(Metashape.Vector([marker["x"],marker["y"]]),True)

class MetashapeTask_ReorientSpecial(MetashapeTask):

    """
    Task object for reorienting a model in space based on a pre-defined x and y axis where points on an x-y plane are arbitrarily specified at runtime. It requires:
        input:str a directory of pictures to operate on.
        output:str a place to put the results--this is the parent folder of the picture folder, usually.
        chunkname:str label of the chunk to operate on.

        It assumes that if you are working from a palette of computer readable markers, the name of this palette is already defined in config.json or via
        the UI. NOTE: THIS OPERATION DOES NOT SAVE.

    """
    def __init__(self,argdict:dict):
        print(f"initializing {__name__}")
        super().__init__(argdict)
        self.palette_info = None 
        pal = Configurator.getConfig().getProperty("photogrammetry","palette") 
        self.palette_name = pal if pal != "none" else None
        self.axes=None

    def __repr__(self):
        return "Metashape Task: Reorient Model--SPECIAL"
    
    def setup(self):
        success, code = super().setup()
        if not success:
            return success, code
        if self.chunk and self.palette_name:
            print("Calculating axes.")
            palettedict = util.load_palettes()
            self.palette_info = palettedict[self.palette_name]
            if self.chunk.model:
                self.axes, planedata, xaxisdata = ModelHelpers.find_axes_from_markers_in_plane(self.chunk,self.palette_info)
                if self.axes and planedata and xaxisdata:
                    getGlobalLogger(__name__).info("Found axis from markers: axes: %s.",self.axes)
                    getGlobalLogger(__name__).info("Found planes: %s to %s to %s : (%s,%s,%s)", planedata[0]['name'],planedata[1]['name'],planedata[2]['name'],planedata[0]['pos'],planedata[1]['pos'],planedata[2]['pos'])
                    getGlobalLogger(__name__).info("Found x-axis: %s to %s : (%s,%s)",xaxisdata[0]['name'],xaxisdata[1]['name'],xaxisdata[0]['pos'],xaxisdata[1]['pos'])
                else:
                    success = False
                    code = ErrorCodes.NO_AXES
            else:
                success = False
                code = ErrorCodes.NO_MODEL_FOUND
        return success, code
        
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success, code = super().execute()
        if success:
            if self.chunk.orthomosaic:
                #An orthomosaic already existing on this chunk means its whole downstream pipeline
                #(this reorientation, the cross-chunk AlignChunks pass, model, and orthomosaic) already
                #completed successfully on some earlier run. Re-running reorientation here recomputes
                #axes from the chunk's *current* marker positions and replaces the whole transform from
                #scratch, which isn't perfectly numerically idempotent--repeated re-runs against an
                #already-finished project were observed to measurably degrade previously-good
                #cross-band marker alignment over several passes. Skip it once there's nothing left to do.
                getGlobalLogger(__name__).info("Chunk %s already has an orthomosaic; skipping re-orientation.",self.chunkname)
            elif len(self.axes)==0:
                getGlobalLogger(__name__).warning("No axes on which to orient chunk %s",self.chunkname)
            else:
                getGlobalLogger(__name__).info("Reorienting chunk %s according to markers on palette.",self.chunkname)
                ModelHelpers.align_markers_to_axes(self.chunk,self.axes,1.0)
                ModelHelpers.move_model_to_world_origin(self.chunk)
        return success, code
    
class MetashapeTask_CopyMarkersFromChunk(MetashapeTask):
    """
    Task object for copying a set of markers from one set of identical images to another. Use for when you have a camera with two sensors taking two imagesets where one imageset doesn't record the black and white
    color data of the targets.
    -This expects an argdict on init with: {"otherchunk":The name of the chunk you want to copy the markers from.
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
       super().__init__(argdict)
       self.otherchunkname = argdict["otherchunk"]
       self.otherchunk=None
 
    def __repr__(self):
        return "Metashape Task: Copy markers from a specified second chunk"
    
    def setup(self):
        success, code = super().setup()
        if success and self.chunk:
            doc = self.doc
            for c in doc.chunks:
                getGlobalLogger(__name__).info("current chunk is: %s Looking for chunk %s",c.label,self.otherchunkname)
                if c.label == self.otherchunkname:
                    self.otherchunk = c
                    break
            if self.otherchunk is None:
                success = False
                success = ErrorCodes.MISSING_TARGET_CHUNK
        return success, code
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success, code = super().setup()
        if not success:
            return success, code
        if success:
            getGlobalLogger(__name__).info("Copying markers from %s to %s.", self.chunk.label, self.otherchunk.label)
            copyMarkersFromChunkToOtherChunk(self.otherchunk,self.chunk)
        return success, code
    
    def exit(self):
        success, code = super().exit()
        if not success:
            return success, code
        if not len(self.otherchunk.markers)==len(self.chunk.markers):
            success = False
            code = ErrorCodes.MISSING_MARKER
        return success, code
class MetashapeTask_CopyCalibration(MetashapeTask):
    """
    Task object for copying a chunk's self-calibrated sensor calibration onto another chunk's matching
    sensor(s), marking them fixed there. Pair this with a MetashapeTask_ErrorReduction on the destination
    chunk using calibration_mode="fixed", so that chunk solves camera positions only, instead of
    independently self-calibrating its own lens model. Use when several chunks were shot with the same
    physical camera/lens (e.g. the different bands of a multibanded board) and should share one
    calibration instead of each independently self-calibrating--and independently doming--on its own.
    -This expects an argdict on init with: {"sourcechunk": the name of the chunk to copy calibration from.
                                            "chunkname": the name of the chunk you are operating on (destination).
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
        super().__init__(argdict)
        self.sourcechunkname = argdict["sourcechunk"]
        self.sourcechunk = None

    def __repr__(self):
        return "Metashape Task: Copy Calibration From Chunk"

    def setup(self):
        success, code = super().setup()
        if success and self.chunk:
            for c in self.doc.chunks:
                if c.label == self.sourcechunkname:
                    self.sourcechunk = c
                    break
            if self.sourcechunk is None:
                success = False
                code = ErrorCodes.MISSING_TARGET_CHUNK
        return success, code

    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success, code = super().execute()
        if not success:
            return success, code
        getGlobalLogger(__name__).info("Copying calibration from %s to %s.", self.sourcechunk.label, self.chunk.label)
        ModelHelpers.copy_calibration(self.sourcechunk, self.chunk)
        self.doc.save()
        return success, code

    def exit(self):
        success, code = super().exit()
        return success, code

class MetashapeTask_CloneChunk(MetashapeTask):
    """
    Task object for duplicating an already-finished chunk (cameras with their solved transforms,
    tie points, calibration, markers, and model) onto a new chunk, instead of independently
    reconstructing from a re-encoded copy of the same photos. Use for a multibanded band whose
    pointcloud_reference points at another band: setupReferences() in multibanded_boards.py has that
    band reuse the reference band's own converted photos for tie-point matching, so independently
    running alignment/error-reduction/model-building on it is redundant work that can also let the two
    bands' solved geometry (camera poses, and especially the reconstructed mesh used to orthorectify)
    diverge by a small amount--which then shows up as marker misalignment between the two bands'
    orthomosaics. Cloning instead guarantees identical geometry; only the photos get swapped out
    afterward (see MetashapeTask_ChangeImagePathsPerChunk) so the orthomosaic still gets this band's
    own color data.
    -This expects an argdict on init with: {"sourcechunk": the name of the already-finished chunk to clone.
                                            "chunkname": the name of the chunk you want to end up with (destination).
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
        super().__init__(argdict)
        self.sourcechunkname = argdict["sourcechunk"]
        self.sourcechunk = None

    def __repr__(self):
        return "Metashape Task: Clone Chunk"

    def setup(self):
        success, code = super().setup()
        if success is False and code is ErrorCodes.NO_CHUNK:
            #expected the first time this runs--the destination chunk doesn't exist yet.
            success = True
            code = ErrorCodes.NONE
        for c in self.doc.chunks:
            if c.label == self.sourcechunkname:
                self.sourcechunk = c
                break
        if self.sourcechunk is None:
            success = False
            code = ErrorCodes.MISSING_TARGET_CHUNK
        return success, code

    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success, code = super().execute()
        if not success:
            return success, code
        if self.chunk is None:
            getGlobalLogger(__name__).info("Cloning chunk %s as %s.", self.sourcechunk.label, self.chunkname)
            self.chunk = self.sourcechunk.copy()
            self.chunk.label = self.chunkname
            try:
                self.doc.save()
            except OSError as e:
                getGlobalLogger(__name__).error(e)
                success = False
                code = ErrorCodes.METASHAPE_FILE_LOCKED
        return success, code

    def exit(self):
        success, code = super().exit()
        if success and not self.chunk.model:
            success = False
            code = ErrorCodes.NO_MODEL_FOUND
        return success, code

class MetashapeTask_CheckTiePointCount(MetashapeTask):
    """
    Task object for comparing a band's tie point count against an anchor band's, as an early, soft
    warning signal that a band's own reconstruction may be weak. A low tie point count alone doesn't
    reliably predict a broken reconstruction--some bands align fine despite having far fewer points
    than the anchor--so this only logs a warning and never fails the build. It's meant to run right
    after error reduction, before the far more expensive BuildModel/BuildOrthomosaic/BuildTexture
    stages, alongside MetashapeTask_CheckMarkerConsistency, which is the check that actually catches a
    broken reconstruction.
    -This expects an argdict on init with: {"anchorchunk": the name of the chunk to compare tie point
                                            count against.
                                            "threshold": ratio (0-1) below which to warn--e.g. 0.5 warns
                                            when this band has under half the anchor's tie points. Defaults
                                            to 0.5.
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
        super().__init__(argdict)
        self.anchorchunkname = argdict["anchorchunk"]
        self.anchorchunk = None
        self.threshold = argdict.get("threshold", 0.5)

    def __repr__(self):
        return "Metashape Task: Check Tie Point Count Against Anchor Band"

    def setup(self):
        success, code = super().setup()
        if success:
            for c in self.doc.chunks:
                if c.label == self.anchorchunkname:
                    self.anchorchunk = c
                    break
            if self.anchorchunk is None:
                success = False
                code = ErrorCodes.MISSING_TARGET_CHUNK
        return success, code

    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success, code = super().execute()
        if success:
            mine = len(self.chunk.tie_points.points) if self.chunk.tie_points else 0
            anchors = len(self.anchorchunk.tie_points.points) if self.anchorchunk.tie_points else 0
            ratio = (mine / anchors) if anchors > 0 else 1.0
            if ratio < self.threshold:
                getGlobalLogger(__name__).warning(
                    "Chunk %s has only %s tie points vs anchor chunk %s's %s (%.0f%% of anchor, below the %.0f%% warning threshold). "
                    "This band's reconstruction may be weak--worth double-checking its alignment once the build finishes.",
                    self.chunk.label, mine, self.anchorchunk.label, anchors, ratio*100, self.threshold*100)
        return success, code

class MetashapeTask_CheckMarkerConsistency(MetashapeTask):
    """
    Task object for catching a broken per-band reconstruction early, before the expensive BuildModel/
    BuildOrthomosaic/BuildTexture stages run. Compares this chunk's own marker-to-marker distances
    (each chunk's own marker.position run through that chunk's own chunk.transform.matrix, to put both
    in real-world meters--marker.position alone is in the chunk's raw, arbitrary-scale bundle-adjustment
    units, not real-world units; only chunk.transform carries the scale bars' calibration) against an
    anchor band's--a band's own reconstruction can silently fold or collapse in weak-texture imagery (e.g. UV)
    while still producing plausible-looking camera positions, so a legitimate reconstruction should
    reproduce the anchor's marker-to-marker distances closely. Any pair that's off by more than
    `threshold` fails the build here instead of quietly propagating into a distorted, mis-oriented
    orthomosaic several build stages later.
    -This expects an argdict on init with: {"anchorchunk": the name of the chunk to compare marker
                                            distances against.
                                            "threshold": maximum allowed fractional deviation from the
                                            anchor's distance for any marker pair before failing, e.g. 0.2
                                            allows up to 20% off. Defaults to 0.2.
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
        super().__init__(argdict)
        self.anchorchunkname = argdict["anchorchunk"]
        self.anchorchunk = None
        self.threshold = argdict.get("threshold", 0.2)
        self.badpairs = []

    def __repr__(self):
        #BaseTask.__init__ calls __repr__ to set _statename before MetashapeTask.__init__ has set
        #self.chunkname (it's assigned after the super().__init__() call that reaches BaseTask), so
        #this needs a safe fallback for that one bootstrap call--chunkname is set by the time __repr__
        #is called again for real, e.g. in executeTasklist's failure log line.
        return f"Metashape Task: Check Marker Consistency Against Anchor Band ({getattr(self, 'chunkname', '?')})"

    def setup(self):
        success, code = super().setup()
        if success:
            for c in self.doc.chunks:
                if c.label == self.anchorchunkname:
                    self.anchorchunk = c
                    break
            if self.anchorchunk is None:
                success = False
                code = ErrorCodes.MISSING_TARGET_CHUNK
        return success, code

    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success, code = super().execute()
        if success:
            minetransform = self.chunk.transform.matrix
            anchortransform = self.anchorchunk.transform.matrix
            mine = {m.label: minetransform.mulp(m.position) for m in self.chunk.markers if m.position is not None}
            anchor = {m.label: anchortransform.mulp(m.position) for m in self.anchorchunk.markers if m.position is not None}
            shared = sorted(mine.keys() & anchor.keys())
            self.badpairs = []
            for a, b in itertools.combinations(shared, 2):
                anchordist = (anchor[a]-anchor[b]).norm()
                if anchordist < 1e-6:
                    continue
                minedist = (mine[a]-mine[b]).norm()
                deviation = abs(minedist-anchordist)/anchordist
                if deviation > self.threshold:
                    self.badpairs.append((a, b, minedist, anchordist, deviation))
            if self.badpairs:
                success = False
                code = ErrorCodes.MARKER_CONSISTENCY_FAILURE
                #Map each flagged marker back to the photos it was actually detected in, so the failure
                #message can point at specific pictures to add bridging markers to/between, instead of
                #just naming the abstract marker pair.
                markersbylabel = {m.label: m for m in self.chunk.markers}
                allphotos = set()
                for a, b, minedist, anchordist, deviation in self.badpairs:
                    photosa = sorted(cam.label for cam in markersbylabel[a].projections.keys())
                    photosb = sorted(cam.label for cam in markersbylabel[b].projections.keys())
                    allphotos.update(photosa)
                    allphotos.update(photosb)
                    getGlobalLogger(__name__).error(
                        "Chunk %s: distance between %s and %s is %.4f, but anchor chunk %s has %.4f (%.0f%% off, threshold %.0f%%). "
                        "%s appears in photos %s; %s appears in photos %s. "
                        "This band's own reconstruction looks broken (e.g. folded/collapsed in weak-texture imagery)--"
                        "consider adding manual tie points/markers bridging the photos between these two groups before re-aligning.",
                        self.chunk.label, a, b, minedist, self.anchorchunk.label, anchordist, deviation*100, self.threshold*100,
                        a, photosa, b, photosb)
                getGlobalLogger(__name__).error(
                    "Chunk %s: photos involved in the flagged marker pairs above (start here when placing manual bridging markers): %s",
                    self.chunk.label, sorted(allphotos))
        return success, code

class MetashapeTask_ResizeBoundingBox(MetashapeTask):
    """
    -This is a task for resizing a bounding box given a centerpoint and a Metashape vector of width,depth,height
    -This expects an argdict on init with: {"width_depth_height":MEtashape vector with float members detailing the dimensions of the box in meters.
                                            "centerpoint": Metashape vector with x,y,z of the box centerpoint
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
       super().__init__(argdict)
       self.width_depth_height = argdict["width_depth_height"]
       self.centerpoint = argdict["centerpoint"]
 
    def __repr__(self):
        return "Metashape Task: SetBoundingBoxDimensions"
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        
        getGlobalLogger(__name__).info("At least I got here.")
        #transform local coordinates to the coordinate reference system if there is one.
        success, code = super().execute()
        if not success:
            return success, code
        region = self.chunk.region
        region.size = self.width_depth_height
        region.center = self.centerpoint 
        self.chunk.region = region
        #set the bounding box rotation to be the same as the object.
        self.doc.save()
        return success, code
    
class MetashapeTask_CopyBoundingBoxToChunks(MetashapeTask):
    """
    Task object for copying a set of markers from one set of identical images to another. Use for when you have a camera with two sensors taking two imagesets where one imageset doesn't record the black and white
    color data of the targets.
    -This expects an argdict on init with: {chunklist : list of chunks to copy boundingbox of the current chunk to
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
       super().__init__(argdict)
       self.chunklist = argdict["chunklist"]
 
    def __repr__(self):
        return "Metashape Task: Copy Bounding Box to Chunks."
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success, code = super().execute()
        if not success:
            return success, code
        region = self.chunk.region
        rrot = region.rot
        rcent = region.center
        rsize = region.size
        mctransform = self.chunk.transform.matrix
        chunks = [x for x in self.doc.chunks if x.label in self.chunklist]
        for c in chunks:
            cregion = c.region
            print(c.label)
            T = c.transform.matrix.inv()*mctransform #map the current chunk's space to the main chunk's space and put that transform in t.
            R  = Metashape.Matrix([[T[0,0],T[0,1],T[0,2]],
                                [T[1,0],T[1,1],T[1,2]],
                                [T[2,0],T[2,1],T[2,2]],
                                ]) #remove the rotation matrix from the transform matrix manually.
            scale = R.row(0).norm() #the rows are the original x,y,z axes M*Rot*Scale Calculating the length of one of them gets the scale factof IF they are uniformly scaled.
            R = R * (1/scale) #remove the scale from the rotation matrix to get a pure rotation.
            cregion.rot = R*rrot # #region becomes therotation of the current chunk*the rotation of the region.
            newc = T.mulp(rcent) #multiply the old object center by the new chunk's transform.
            cregion.size = rsize*scale  #transfer the old bounding box center into the current chunk's local coordinates.
            cregion.center = newc
            c.region = cregion

        marker = self.chunk.addMarker() #this is a nasty hack because metashape won't actually save after some minor changes.
        self.doc.save()
        self.chunk.remove(marker)
        self.doc.save()
        return self,code
    
    def exit(self):
        success,code = super().exit()
        return success,code


class MetashapeTask_RotateBoundingBox(MetashapeTask):
    """
    Task object for copying a set of markers from one set of identical images to another. Use for when you have a camera with two sensors taking two imagesets where one imageset doesn't record the black and white
    color data of the targets.
    -This expects an argdict on init with: {xyz: list with floats representing x,y,z in DEGREES
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
       super().__init__(argdict)
       self.rot_x_y_z = argdict["xyz"]
 
    def __repr__(self):
        return "Metashape Task: Set Boundingbox Rotation"
    

    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success,code= super().execute()
        if not success:
            return success, code
        getGlobalLogger(__name__).info("At least I got here.")
        ModelHelpers.rotate_boundingbox(self.chunk,self.rot_x_y_z)
        return success,code

class MetashapeTask_ImportModel(MetashapeTask):
    """
    This is a task for importing a saved out model as the model of an object, with the expectation that you want to project pictures onto it.
    -This expects an argdict on init with: {"modelfilename": full path of the model to load.
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
        super().__init__(argdict)
        self.modelfilename = Path(argdict["modelfilename"])
      
    def __repr__(self):
        return "Metashape Task: ImportModel"
   
    def setup(self):
        success, code = super().setup()
        if not success:
            return success, code
        if not self.modelfilename.is_file():
            success = False
            code = ErrorCodes.INVALID_FILE
        return success,code
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success,code = super().execute()
        if not success:
            return success, code
        #transform local coordinates to the coordinate reference system if there is one.
        self.chunk.importModel(str(self.modelfilename),
                               Metashape.ModelFormat.ModelFormatPLY if self.modelfilename.suffix.upper()==".PLY" else Metashape.ModelFormat.ModelFormatOBJ,
                                replace_asset = True)
        if not self.chunk.model:
            success = False
            code = ErrorCodes.NO_MODEL_FOUND

        return success, code
        #set the bounding box rotation to be the same as the object.


class MetashapeTask_ChangeImagePathsPerChunk(MetashapeTask):
    """
     Task object for replacing images on a chunk with images in a different directory.
    -This expects an argdict on init with: {"replace_these: a list of images to replace
                                            "to_replace_with":a 1:1 list of image paths to replace the existing images with.
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}
    """
    def __init__(self, argdict:dict):
       super().__init__(argdict)
       self.replacenames = argdict["to_replace_with"]
       self.imagestoreplace = argdict["replace_these"]
    
    def setup(self):
        success,code = super().setup()
        if success:
            for image in self.imagestoreplace:
                if not Path(image).exists():
                    success = False
                    code = ErrorCodes.INVALID_FILE
                    break
        return success, code

    def __repr__(self):
        return "Metashape Task: Replace images in chunk with others."
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success,code = super().execute()
        if success:
            for c in self.chunk.cameras:
                if c.type == Metashape.Camera.Type.Regular:
                    for i,cams in enumerate(self.imagestoreplace):
                        #Resolve to absolute before comparing/storing: camera.photo.path is whatever
                        #was absolute (or resolved to absolute) when its chunk was first built, while
                        #self.imagestoreplace is recomputed fresh on every run from this run's own
                        #sourcedir/projectdir CLI args--if those happen to be given as relative paths
                        #on a later run against an already-built project, a raw string compare here
                        #would never match even though both sides name the same real file.
                        temp = Path(cams).resolve()
                        metashapepath = Path(c.photo.path).resolve()
                        if temp==metashapepath:
                            newpath = str(Path(self.replacenames[i]).resolve())
                            photocopy = c.photo.copy()
                            photocopy.path  = newpath
                            c.photo = photocopy
                            getGlobalLogger(__name__).info("replacing %s with %s",metashapepath,newpath)
                            break
            marker = self.chunk.addMarker() #this is a nasty hack because metashape doesn't save paths if that's all you do before you save.
            self.doc.save()
            self.chunk.remove(marker)
            self.doc.save()

        return success,code
    
    def exit(self):
        success, code = super().exit()
        if success:
            replacenames = [str(r.name) for r in self.replacenames]
            for c in self.chunk.cameras:
                if c.type == Metashape.Camera.Type.Regular:
                    pt = str(Path(c.photo.path).name)
                    if pt not in replacenames:
                        success = False
                        code = ErrorCodes.REPLACE_IMAGES_FAILURE
                        break
        return success,code
                    

class MetashapeTask_ResizeBoundingBoxFromMarkers(MetashapeTask):
      
    def findTargetFromNumber(self, num:int):
        getGlobalLogger(__name__).info("finding target for marker %s.", num)
        for m in self.chunk.markers:
            if m.label == f"target {num}":
                return m
        getGlobalLogger(__name__).error("failed to find marker \"target %s\"", num)
        return None
    
    def __init__(self,argdict:dict):
        getGlobalLogger(__name__).info("initializing %s",__name__)
        super().__init__(argdict)
        self.dimensions = argdict["dimensionmarkers"]
        self.widthmarkers=[]
        self.depthmarkers=[]

    def __repr__(self):
        return "Metashape Task: Set the dimensions of the bounding box based on specified markers"
    
    def setup(self):
        success,code =  super().setup()
        self.widthmarkers = [self.findTargetFromNumber(self.dimensions[f]) for f in range(0,2)]
        self.depthmarkers = [self.findTargetFromNumber(self.dimensions[f]) for f in range(2,4)]
        success = success and len(self.widthmarkers)==2 and len(self.depthmarkers)==2
        if None in self.widthmarkers or None in self.depthmarkers:
            success = False
            code = ErrorCodes.MISSING_MARKER
        return success,code
    
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success, code = super().execute()
        if success:
            wv = self.widthmarkers[1].position-self.widthmarkers[0].position
            #calculate width and depth from markers. This assumes that markers are placed on at least three sides of the object
            width = math.sqrt(wv.x**2 +wv.y**2 +wv.z**2) #get the magnitude of the vector between point 1 and 2.
            dv = self.depthmarkers[1].position-self.depthmarkers[0].position
            depth =math.sqrt(dv.x**2 +dv.y**2 +dv.z**2)*2 
            centerxy = (self.widthmarkers[1].position-self.depthmarkers[1].position)/2 + self.depthmarkers[1].position 
            #calculate centerpoint. This assumes that the second depth and width markers are diagonal from each other and on opposite sides of the object.
            #it's very specific to FMNH setup which only puts markers on three sides of the object.
            print(f"{self.widthmarkers[1].label}={self.widthmarkers[1].position}, {self.depthmarkers[1].label} = {self.depthmarkers[1].position}")
            height = 5 #hardcoding it for now because there are no height markers.
            #Adding some fudge factors to width and depth so it's not cutting through the markers on the top and side.
            wdh = Metashape.Vector((width+2.0,depth+2.0,height))
            tasklist = []
            tasklist.append( MetashapeTask_ResizeBoundingBox({"input":"","output":self.output ,"projectname":self.projectname,"chunkname":self.chunk.label,"width_depth_height":wdh,"centerpoint":centerxy}))  
            tasklist.append( MetashapeTask_RotateBoundingBox({"input":"","output":self.output,"projectname":self.projectname,"chunkname":self.chunk.label,"xyz":[0,0,0]}))    #just hardcoding it for now.
            for task in tasklist:
                subsuccess, subcode = task.setup()
                if subsuccess:
                    subsuccess, subcode = task.execute()
                    if subsuccess:
                        subsuccess, subcode = task.exit()
                if subsuccess is False:
                    success = subsuccess
                    code = subcode
                    break   
        return success,code
        

class MetashapeTask_DetectMarkersFromThresholdedImage(MetashapeTask_DetectMarkers):
    """
    Task object for detecting markers from a thresholded image set. This takes an image set, thresholds them, detects markers,
    then copies the markers back onto the original images. Why would you ever want to do this? Well, say you have an image with UV light
    in purple and black that is too dark to detect white on black targets (which are blue on deeper blue anyway). This converts to black and white, 
    detects markers, then copies the markers back onto your blue and purple image.
    -This expects an argdict on init with: {"threshold":The intensity above which a grayscale pixel ought to be white rather than black.
                                            "chunkname": the name of the chunk you are operating on.
                                            "projectname": the name of the psz file without the extension.
                                            "input": The directory you put the source images in.
                                            "output": usually, this is the base directory of the project where you want the psz file and all the output images to be saved.}

    """
    def __init__(self,argdict:dict):
        print(f"initializing {__name__}")
        super().__init__(argdict)
        self.oldchunk = self.chunk
        self.threshold = argdict["threshold"]
        self.deletetemp = True

    def __repr__(self):
        return "Metashape Task: Detect Markers from Thresholded Images"
    
    def setup(self):
        success,code = super().setup()
        if success and self.chunk:
            doc = MetashapeFileSingleton.getMetashapeDoc(self.projectname,self.output)
            currentworkingdir = Path(doc.path).parent
            photostomunge=[]
            tempdir = Path(currentworkingdir,"temp")
            try:
                mkdir(tempdir)
            except FileExistsError:
                self.deletetemp = False
            for camera in self.chunk.cameras:
                impath = camera.photo.path
                cam = cv2.imread(impath)
                bw = cv2.cvtColor(cam,cv2.COLOR_BGR2GRAY)
                _,mask = cv2.threshold(bw,self.threshold,255,cv2.THRESH_BINARY)
                outdir =str(Path(tempdir,Path(impath).name))
                photostomunge.append(outdir)
                cv2.imwrite(str(outdir),mask)
            self.oldchunk = self.chunk
            self.chunk= doc.addChunk()
            self.chunkname = self.chunk.label = "Tempchunk"
            doc.chunk = self.chunk
            for photo in photostomunge:
                if Path(photo).suffix.upper() ==".JPG":
                    self.chunk.addPhotos(photo)
           
        return success, code
        
    @timed(Statistic_Event_Types.EVENT_BUILD_MODEL)
    def execute(self):
        success,code = super().execute()
        if success:
            doc = MetashapeFileSingleton.getMetashapeDoc(self.projectname,self.output)
            copyMarkersFromChunkToOtherChunk(self.chunk,self.oldchunk)
             #cleanup
            tempchunk = self.chunk
            self.chunk =  doc.chunk = self.oldchunk
            self.chunkname = doc.chunk.label
            doc.remove(tempchunk)
            doc.save()
            if self.deletetemp:
                shutil.rmtree(Path(Path(doc.path).parent,'temp'))
        return success,code
    
    def exit(self):
        success,code = super().exit()
        if success:
            if self.deletetemp:
                doc = MetashapeFileSingleton.getMetashapeDoc(self.projectname,self.output)
                if Path(Path(doc.path).parent,'temp').is_dir():
                    success = False
                    code = ErrorCodes.FAILURE_TO_REMOVE_FILE
            if success and (self.chunk.markers is None or len(self.chunk.markers) ==0):
                success = False
                code = ErrorCodes.MISSING_MARKER
  
        return success, code
