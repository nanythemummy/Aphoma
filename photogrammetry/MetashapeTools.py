"""This module contains code used to orchestrate building a model with metashape. The code in here should tell metashape to do stuff.
Code requiring number crunching probably ought to go in the associated utility class, ModelHelpers.py
"""

import argparse
import traceback
import os
import Metashape
import photogrammetry.ModelHelpers as ModelHelpers
from util.InstrumentationStatistics import InstrumentationStatistics,Statistic_Event_Types
from util.util import get_export_filename, load_palettes
from util.PipelineLogging import getLogger as getGlobalLogger
from util.Configurator import Configurator


def get_logger():
    return getGlobalLogger(__name__)

def load_photos(chunk, projectdir:str, photodir:str):
    """Tells Metashape to load the photos and masks in specified directories to the given chunk.
    Parameters:
    ----------
    chunk: the chunk to which the photos need to be added.
    projectdir: the directory of the project
    photodir: the directory from which to take the photos.
    maskpath: the path at which the mask files are stored.
    """


    images = os.listdir(photodir)
    get_logger().info("Loading images from %s", photodir)
    for i in images:
        if os.path.splitext(i)[1].upper() in [".JPG", ".TIFF",".TIF"]:
            chunk.addPhotos(os.path.join(photodir,i))

def load_masks(chunk,maskpath:str,projectdir:str):
    if not maskpath or not os.path.exists(os.path.join(projectdir,maskpath)):
        get_logger().warning("Mask path %s doesn't exist or wasn't passed corectly. Failing loading masks.",maskpath)
        return
    maskpath = os.path.join(projectdir,maskpath)
    files = os.listdir(maskpath)
    if len(files)>0:
        get_logger().info("Loading masks from %s", maskpath)
        ext = os.path.splitext(files[0])[1] #get the ext
        template = f"{maskpath}{os.sep}{{filename}}{ext}"
        chunk.generateMasks(template,Metashape.MaskingMode.MaskingModeFile)

def build_basic_model(photodir:str, projectname:str, projectdir:str, decimate = True, maskoption = 0):
    """Uses Agisoft Metashape to build and export a model using the photos in the directory specified.
    Parameters:
    ------------------
    photodir: The directory where the photographs to build into a model are stored.
    projectname: the name of the project. This will be used to name the metashape file and the chunks inside it.
    projectdir: the base directory where the metashape file will be stored.
    config: the section of config.json containing the photogrammetry configurations, the value for the key "photogrammetry"
    decimate: If this is set to true, a new chunk will be made in which the model is decimated to the configured number of triangles.
    """
    get_logger().info('Building model %s in location %s from photos in %s', projectname, photodir,projectdir)
    config = Configurator.getConfig()
    sid = InstrumentationStatistics.getStatistics().timeEventStart(Statistic_Event_Types.EVENT_BUILD_MODEL)
    #Open a new document
    projectpath = os.path.join(projectdir,projectname+".psx")
    outputpath = os.path.join(projectdir,config.getProperty("photogrammetry","output_path"))
    
    maskpath =config.getProperty("photogrammetry","mask_path") if maskoption !=0 else None
    palette =  load_palettes()[config.getProperty("photogrammetry","palette")]
    if not os.path.exists(outputpath):
        os.mkdir(outputpath)
    doc = Metashape.Document()
    try:
        if os.path.exists(projectpath):
            get_logger().info("Loading project %s",projectpath)
            doc.open(path=projectpath)
        doc.save(path=projectpath)
        #add  a new chunk
        current_chunk=None
        if len(doc.chunks)==0:
            current_chunk = doc.addChunk()
            current_chunk.label=projectname
            doc.save()      
            get_logger().info('Added chunk %s.', projectname)
        else:
            current_chunk=doc.chunks[0]
            get_logger().info('A Chunk called %s already exists. Building it.', current_chunk.label)

        #build sparse cloud.
        if len(current_chunk.cameras)==0:
            load_photos(current_chunk,projectdir,photodir)
            load_masks(current_chunk,maskpath,projectdir)
            get_logger().info("Matching photos.")


        if not current_chunk.point_cloud:   
            current_chunk.matchPhotos(downscale=config.getProperty("photogrammetry","sparse_cloud_quality"),
                generic_preselection=True,
                reference_preselection=True,
                reference_preselection_mode=Metashape.ReferencePreselectionMode.ReferencePreselectionSource,
                filter_mask=(maskpath!=None),
                mask_tiepoints=False,
                filter_stationary_points=True,
                tiepoint_limit=0,
                reset_matches=False)
            get_logger().info("Aligning Cameras.")
            current_chunk.alignCameras()
            doc.save()
                    #detect markers.
        if palette:
            get_logger().info("Finding markers as defined in %s.", config.getProperty("photogrammetry","palette"))
            if not current_chunk.markers:
                ModelHelpers.detect_markers(current_chunk,palette["type"])
                doc.save()
        if current_chunk.point_cloud and not current_chunk.model:
            thresholds = config.getProperty("photogrammetry","error_thresholds")
            ModelHelpers.refine_sparse_cloud(doc, current_chunk,thresholds)
            doc.save()
        
        #build model.
        if not current_chunk.model:
            facecount = None or config.getProperty("photogrammetry","custom_face_count")
            targetfacecount = facecount or 200000
            facecountconst = Metashape.FaceCount.CustomFaceCount if facecount else Metashape.FaceCount.HighFaceCount
            get_logger().info("Building Depth Maps.")
            current_chunk.buildDepthMaps(downscale=config.getProperty("photogrammetry","model_quality"), filter_mode = Metashape.FilterMode.MildFiltering)
            get_logger().info("Building Model.")
            current_chunk.buildModel(source_data = Metashape.DataSource.DepthMapsData, 
                                    face_count = facecountconst,
                                    face_count_custom = targetfacecount)
            doc.save()
        #detect build scalebars
        if palette:
            if "scalebars" in palette.keys() and not current_chunk.scalebars:
                get_logger().info("Attempting to define scalebars.")
                if palette["scalebars"]["type"] == "explicit":
                    ModelHelpers.build_scalebars_from_list(current_chunk,palette["scalebars"]["bars"])
                elif palette["scalebars"]["type"]=="sequential":
                    ModelHelpers.build_scalebars_from_sequential_targets(current_chunk,palette["scalebars"])
                doc.save() 
        #remove blobs.
        get_logger().info("Cleaning up detached geometry.")
        ModelHelpers.cleanup_blobs(current_chunk)    
        doc.save()    
        #close holes
        get_logger().info("Closing holes.")
        ModelHelpers.close_holes(current_chunk)
        doc.save()
        #decimate model
        if decimate and len(doc.chunks)<2:
            get_logger().info("Building a lower poly version of the model from a duplicate chunk.")
            newchunk = current_chunk.copy(items=[Metashape.DataSource.DepthMapsData, Metashape.DataSource.ModelData], keypoints=True)
            lrpolycount = int(config.getProperty("photogrammetry","low_res_poly_count"))
            newchunk.label = f"{current_chunk.label} lowpoly {lrpolycount/1000}K"
            newchunk.decimateModel(replace_asset=True,face_count=lrpolycount)
        #build texture for each chunk.
        for c in doc.chunks:
            if not c.model.textures:
                get_logger().info("Building UV Map and Texture for chunk %s",c.label)
                c.buildUV(page_count=config.getProperty("photogrammetry","texture_count"), texture_size=config.getProperty("photogrammetry","texture_size"))
                c.buildTexture(texture_size=config.getProperty("photogrammetry","texture_size"), ghosting_filter=True)
                doc.save()
        #reorient model and export.
        for c in doc.chunks:
            #for now, don't save after model reorient.
            if palette:
                reorient_model(c,palette)
            get_logger().info("Finished building.") 
            labelname = c.label.replace(" ","")
            ext = config.getProperty("photogrammetry","export_as")
            outputtypes = []
            if not ext == "none":
                if ext == "all":
                    outputtypes += ['.ply','.obj']
                else:
                    outputtypes.append(ext)
                for extn in outputtypes:
                    name = get_export_filename(labelname,extn)
                    get_logger().info("Now, exporting chunk %s as %s",c.label,name )
                    c.exportModel(path=f"{os.path.join(outputpath,name)}{extn}",
                                texture_format = Metashape.ImageFormat.ImageFormatPNG,
                                embed_texture=(extn=="ply") )

        InstrumentationStatistics.getStatistics().timeEventEnd(sid)
    except Exception as e:
        get_logger().error(e)
        print(e)
        print(traceback.format_exc())
        raise e
    finally:
        doc = Metashape.Document() #basically forcing metashape to close the old document by starting a new one. Sigh. Metashape document has no
        #context manager and no close method and tends to leave a lock file or leave its .file folder readonly.


def reorient_model(chunk,palette):
    """Rotates the object so that the axes on the marker pallette are in line with the world xyz axes and so that the object
    is centered on the origin.
    
    Parameters:
    ----------
    chunk: the chunk wht the model on which we are operating.
    """
    axes = ModelHelpers.find_axes_from_markers(chunk,palette)
    if len(axes)==0:
        get_logger().warning("No axes on which to orient chunk %s",chunk.label)
        return
    else:
        
        get_logger().info("Reorienting chunk %s according to markers on palette.",chunk.label)
        ModelHelpers.align_markers_to_axes(chunk,axes)
        ModelHelpers.move_model_to_world_origin(chunk)

if __name__=="__main__":

    
    def command_build_model(args):
        """Command line interface for building a one-off model. Can also be run from the parent directory via photogrammetryScripts.py
        Parameters:
        -------------
        args: the args passed in from the command line for the orient command.
        """
        build_basic_model(args.photos,args.jobname,args.outputdirectory)
    
    def orient_model(args):
        """Command line interface for reorienting the model.

        Parameters:
        ------------
        args: the args passed in from the command line for the orient command.
        """
        doc = Metashape.Document()
        cfg = Configurator.getConfig()
        palette =  load_palettes()[cfg.getProperty("photogrammetry","palette")]

        if os.path.exists(args.psxpath):
            doc.open(path=args.psxpath)
        reorient_model(doc.chunks[0],palette)
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="MetashapeTools")
    subparsers = parser.add_subparsers(help="Sub-command help")
    
    buildparser = subparsers.add_parser("build", help="Build the model in the given psx file.")
    orientparser = subparsers.add_parser("orient", help="Orients a model on origin, and rotates it into position if markers are present.")

    buildparser.add_argument("jobname", help="The name of the project")
    buildparser.add_argument("photos", help="Place where the photos in tiff or jpeg format are stored.")
    buildparser.add_argument("outputdirectory", help="Where the intermediary files for building the model and the ultimate model will be stored.")
    buildparser.add_argument("config", help="The location of config.json")
    buildparser.set_defaults(func=command_build_model)

    orientparser.add_argument("psxpath", help="psx file to load")
    orientparser.add_argument("config", help="The location of config.json")
    orientparser.set_defaults(func=orient_model)

    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()
