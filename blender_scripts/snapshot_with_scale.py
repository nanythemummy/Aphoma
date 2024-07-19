# This script is adapted from the demo script background_job.py

import os
import bpy


def example_function(inputpath, scalepath, render_path):
    # Clear existing objects.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    #import ply file. Note that blender gets ornery about windows paths so we convert this to a unix one.
    #it's apparently cool with drive letters, it just wants the unix seperator.
    objectname = os.path.join(inputpath).stem
    inputpath.replace("\\","/")
    if inputpath.lower().endswith("obj"):
        bpy.ops.wm.obj_import(filepath="inputpath")
    elif inputpath.lower().endswith("ply"):
        bpy.ops.wm.ply_import(filepath = "inputpath")

    


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
        help="The ply or file containing the scale to place in the scene."
                        )
    parser.add_argument(
        "-r", "--render", dest="render_path", metavar='FILE',
        help="Render an image to the specified path",
    )

    args = parser.parse_args(argv)  # In this example we won't use the args

    if not argv:
        parser.print_help()
        return

    if not args.text:
        print("Error: --text=\"some string\" argument not given, aborting.")
        parser.print_help()
        return

    # Run the snapshot function
    example_function(args.input, args.scale, args.render_path)

    print("Finished!")


if __name__ == "__main__":
    main()
