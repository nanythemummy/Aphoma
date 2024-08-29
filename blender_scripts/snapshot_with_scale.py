# This script is adapted from the demo script background_job.py

import os
from pathlib import Path
from mathutils import *
from math import *
import bpy
def set_background(color:list):
    if not "World" in bpy.data.worlds.keys():
        print("Making new world.")
        bpy.ops.world.new()
    bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[0].default_value=(color[0]/255.0,
                                                                                    color[1]/255.0,
                                                                                    color[2]/255.0,
                                                                                    1)
    bpy.context.scene.world = bpy.data.worlds["World"]
    bpy.context.scene.view_settings.view_transform = "Standard"

def render_snapshot(outputpath, objectname):
    #in the future allow for changing renderer. For now, we will use Eevee for max compatibility, and also because the material
    #we are rendering is not very sophisticated as far as reflections and lights go.
    version = bpy.app.version_string
    versionnum = version.split('.')
    if int(versionnum[0])==4 and int(versionnum[1])>=2:
        bpy.context.scene.render.engine="BLENDER_EEVEE_NEXT"
    else:
        bpy.context.scene.render.engine = "BLENDER_EEVEE"
    

    bpy.context.scene.render.resolution_x=5616
    bpy.context.scene.render.resolution_y=3744
    bpy.context.scene.render.filepath = os.path.join(outputpath,f"{objectname}_render.jpg")
    print(f"Rendering snapshot to {bpy.context.scene.render.filepath}")
    bpy.ops.render.render(write_still=True)

def build_position_scale(scalesizecm,  objectname):
 
    #make the scale
    o = bpy.data.objects[objectname]
    width =o.dimensions.x 
    bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD', location=(0, 0, 0), scale=(0.5,
                                                                                                            scalesizecm,
                                                                                                            2.5))

    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    cube = bpy.data.objects["Cube"]
    cube.name = "Scale"
    blackmat=bpy.data.materials.new(name="blackmat")
    cube.data.materials.append(blackmat)
    cube.active_material.diffuse_color = (0,0,0,1)

    bpy.ops.object.duplicate()
    dupe = bpy.context.view_layer.objects.active
    dupe.name = "Scale_Small"
    bpy.ops.transform.resize(value=(0.95,0.95,0.95))
    whitemat = bpy.data.materials.new(name="whitemat")
    dupe.data.materials[0] =(whitemat)
    dupe.active_material.diffuse_color = (1,1,1,1)

    bpy.ops.object.select_all(action="DESELECT")
    dupe.select_set(True)
    cube.select_set(True)
    bpy.context.view_layer.objects.active = cube
    bpy.ops.object.parent_set(type="OBJECT")

    #make the text that goes on the scale.
    scene = bpy.context.scene
    txt_data = bpy.data.curves.new(name = "fontcurve", type="FONT")
    txto = bpy.data.objects.new(name = "fontobj", object_data = txt_data)
    scene.collection.objects.link(txto)
    txt_data.body = f"{scalesizecm} cm"
    txt_data.extrude = 0.25
    txt_data.size= 1.7
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = bpy.data.objects["fontobj"]
    bpy.context.object.select_set(True)
    bpy.ops.object.convert(target="MESH")
    world_and_local_to_origin("fontobj")
    rotate_on_axis("fontobj","x",90)
    rotate_on_axis("fontobj","z",90)
    bpy.context.object.location[0] +=0.2
    bpy.context.object
#remove the font object from the scale object.
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = bpy.data.objects["Scale"]
    bpy.ops.object.modifier_add(type='BOOLEAN')
    newmodifier = bpy.context.object.modifiers["Boolean"]
    newmodifier.object=bpy.data.objects["fontobj"]
    newmodifier.solver="FAST"
    newmodifier.operation = "DIFFERENCE"
    bpy.ops.object.modifier_apply(modifier="Boolean")
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = bpy.data.objects["fontobj"]
    bpy.context.object.select_set(True)
    bpy.ops.object.delete(use_global=False,confirm=False)
    bpy.context.view_layer.objects.active = bpy.data.objects["Scale"]
    bpy.data.objects["Scale"].select_set(True)
    rotate_on_axis("Scale","x",90)
    rotate_on_axis("Scale","z", -90)
    #move the new scale into place.
    bpy.ops.transform.translate(value=(-1*((width/2)+(cube.dimensions.x/2)+0.8),
                                        0.0,
                                        cube.dimensions.z/2))
    return cube.name

def import_position_scale(scalepath, objectname):
    bpy.ops.wm.ply_import(filepath=scalepath)
    scalename = Path(scalepath).stem
    world_and_local_to_origin(scalename)
    rotate_on_axis(scalename,"x",90.0)
    scale_to_cm(scalename)
    sb = bpy.data.objects[scalename]
    bpy.context.view_layer.objects.active=sb
    o = bpy.data.objects[objectname]
    width = o.dimensions.x
    #position the scalebar next to the object with an arbitrary buffer zone, in this case 5.0
    bpy.ops.transform.translate(value=(-1*((width/2)+(sb.dimensions.x/2)+0.05),
                                       0.0,
                                       sb.dimensions.z/2))
    return scalename

def export_model_obj(outputpath,  objectname):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.data.objects[objectname].select_set(True)
    outpath = os.path.join(outputpath,f"{objectname}_copy.obj")
    bpy.ops.wm.obj_export(filepath = outpath, path_mode="COPY")

def save_blend(outputpath,filename):
    outpath = os.path.join(outputpath,f"{filename}.blend")
    bpy.ops.wm.save_as_mainfile(filepath = outpath)

def rotate_on_axis(objectname,axis,degrees):
    axistonum = {"x":0,"y":1,"z":2}
    axisnum = axistonum[axis]
    o = bpy.data.objects[objectname]
    bpy.context.view_layer.objects.active = o
    bpy.context.object.select_set(True)
    bpy.context.object.rotation_euler[axisnum]=degrees*pi/180.0
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

def bottom_to_origin(objectname):
    #blender switches Y up to Z up when you inport so we will be treating height as z instead.
#blender exports Z=up
    o = bpy.data.objects[objectname]
    height = o.dimensions.z 
    bpy.ops.transform.translate(value=(0.0,0.0,height/2))

def world_and_local_to_origin(objectname):
    o = bpy.data.objects[objectname]
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY",center="MEDIAN")

    #this should have been done, but if not...
    loc = o.location
    bpy.ops.transform.translate(value=loc*(-1.0))
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

def scale_to_cm(objectname):
    o = bpy.data.objects[objectname]
    bpy.context.view_layer.objects.active = o
    bpy.ops.transform.resize(value=(0.1,0.1,0.1))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

def setup_camera(targetobjects:list, mainindex:int):
    #make a camera and stick it somewhere arbitrary on the y axis. Rotate it to face 0,0
    bpy.ops.object.camera_add(enter_editmode=False, location = (0.0,-3.0, 0.0), rotation=(pi/2,0.0,0.0))
    bpy.context.scene.camera =bpy.data.objects["Camera"]
    bpy.context.view_layer.objects.active = bpy.context.scene.camera
    bpy.ops.object.select_all(action="DESELECT")
    for target in targetobjects:
        bpy.data.objects[target].select_set(True)
    bpy.ops.view3d.camera_to_view_selected()
    bpy.ops.object.select_all(action="DESELECT")
    #scoot back just a tad more.
    bpy.data.objects["Camera"].select_set(True)
    bpy.context.object.location[1] -=0.5


def setup_light(targetobjectname, lightpos):
    targetobject = bpy.data.objects[targetobjectname]
    bpy.ops.object.light_add(type="SUN", align="WORLD", location=lightpos)
    bpy.ops.object.constraint_add(type="TRACK_TO")
    bpy.context.object.constraints["Track To"].target = targetobject
    bpy.context.object.data.energy = 0.1


def scene_setup(inputpath, scalepath, render_path, flip):

    fliptrue = flip == True
    # Clear existing objects.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    
    bpy.context.scene.unit_settings.length_unit="CENTIMETERS"
    bpy.context.scene.unit_settings.scale_length=0.01
    containingdir = os.path.dirname(inputpath)
    objectname = Path(inputpath).stem
    if inputpath.lower().endswith("obj"):
        bpy.ops.wm.obj_import(filepath=inputpath)
    elif inputpath.lower().endswith("ply"):
        bpy.ops.wm.ply_import(filepath = inputpath)
    world_and_local_to_origin(objectname)
    if fliptrue:
        print("Flipping model.")
        rotate_on_axis(objectname,'x',180.0)
    scale_to_cm(objectname)
    bottom_to_origin(objectname)
    export_model_obj(containingdir,objectname)
    scalename = build_position_scale(5.0,objectname)
    #scalename = import_position_scale(scalepath,objectname)
    setup_camera([objectname,scalename],0)
    setup_light(objectname,bpy.data.objects["Camera"].location)
    set_background([255,255,255])
    save_blend(containingdir,objectname)

    render_snapshot(containingdir,objectname)


def main():
    import sys       # to get command line args
    import argparse  # to parse options for us and print a nice help message

    # get the args passed to blender after "--", all of which are ignored by
    # blender so scripts may receive their own arguments
    argv = sys.argv

    if "--" not in argv:
        argv = []  # as if no args are passed
    else:
        argv = argv[argv.index("--") + 1:]  # get all args after "--"

    # When --help or no args are given, print this help
    usage_text = (
        "Run blender in background mode with this script:"
        "  blender --background --python " + __file__ + " -- [options]"
    )

    parser = argparse.ArgumentParser(description=usage_text)

    # Example utility, add some text and renders or saves it (with options)
    # Possible types are: string, int, long, choice, float and complex.
    parser.add_argument(
        "-i", "--input",dest="input", metavar = "INPUT",
        help="The ply file to import."
    )
    parser.add_argument(
        "-s","--scale",dest="scale",metavar="SCALE",
        help="The obj or file containing the scale to place in the scene."
                        )
    parser.add_argument(
        "-r", "--render", dest="render_path", metavar='FILE',
        help="Render an image to the specified path",
    )
    parser.add_argument(
        "-f","--flipx",dest="flip",metavar="FLIP",
        help="Whether the file needs to be flipped on the X axis because it was generated with the mouth of the vessel down."
    )

    args = parser.parse_args(argv) 
    if not argv:
        parser.print_help()
        return

    # Run the snapshot function
    scene_setup(args.input, args.scale, args.render_path,args.flip=="True")

    print("Finished!")


if __name__ == "__main__":
    main()
