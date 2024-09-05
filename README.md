# Photogrammetry Asset Pipeline (Command-line tools)

Automated asset pipeline for building 3D Models with Photogrammetry, either using an ortery or pictures taken manually. It does the following:
* Listens to a directory where pictures are being uploaded from a camera and transfers them to a different computer via a network drive for processing.
  ** It can do this as a lump or stream them as they come in, using a manifest as a guide for what pics to include.
* Takes a folder of pictures as input, converts them to jpg or tif as needed
* Takes a folder of pictures as input and builds masks for them.
* Takes a folder of images and builds a 3D model with them using Agisoft Metashape. Results are exported in the desired format.
* Rotates the object in the model such that it faces in a specified direction and takes a snapshot using blender of the object next to a scale bar.
* Can build a model using the Ortery in as little as 10 minutes and 30 seconds.
  
## Requirements:
1.  Adobe DNG Converter if you want to use the DNG conversion command.  You can find it on [Adobe's Camera Raw Page](https://helpx.adobe.com/camera-raw/digital-negative.html)
2.  Blender [https://www.blender.org/download/], if you want to take rendered "snapshots" of the emodel for use in the museum database. It has been tested on Blender 4.2.
3.  Agisoft Metashape [https://www.agisoft.com] if you want to use the pipeline to build 3D models.
5.  Adobe Photoshop if you wish to use droplets to build masks. Otherwise, openCV will be used, which is much faster anyway, but less transparent to the end user.
6.  Python 3.11+
7.  Meshlab [https://meshlab.net] if you want to use any of the meshlab automations. (These are still in progress and have been superseeded by the Blender functionality since Meshlab's Python API cannot render out screenshots.)
8. Windows 10 or Windows 11. Theoretically, this will all work on Mac and Linux, too since most of the windows specific functionality can be configured. However, I have not yet had the opportunity to test extensively on MacOS or Linux.

## Setup:
In the Windows cmd terminal, powershell terminal, or Unix terminal, do the following on both the Ortery computer and the comptuer you will be using to do the model building. Windows commands will be given. If you are familiar with the MacOS/Linux terminal you should be able to figure out the equivalents.

### Sync the Git Code and Set Up a Virtual Environment

  ```
  git clone https://github.com/nanythemummy/museumcode.git
  cd museumcode
  python -m venv venv
  venv\scripts\activate.bat
  ```
### Install the dependencies 
These are all in requirements text except for metashape, which you cannot get from pip. Download and Install the Metashape standalone python module from the [Agisoft Download Page](httpw://www.agisoft.com/downloads) Note that you must have a license for metashape professional for this to work. Note that if you are using Python 3.12, as of 6/14/2024, they have not made the module explicitly compatible with it yet. It does in fact work. You just need to rename the file from Metashape-2.1.1-cp37.cp38.cp39.cp310.cp311-none-win_amd64 to Metashape-2.1.1-cp37.cp38.cp39.cp310.cp311.cp312-none-win_amd64
Now, install the wheel for metashape and then install the requirements in the normal way. The following assumes you downloaded the metashape wheel into the downloads directory.

```
  pip install -r requirements.txt
  pip install %USERPROFILE%\Downloads\Metashape-2.1.1-cp37.cp38.cp39.cp310.cp311.cp312-none-win_amd64.whl
```

### Configure config.json
1. Make a copy of config_template.json and name it config.json
2. Add config.json to .gitignore so you don't end up checking it in if you intend to work on this code.
3. The following values should be filled out before you start. I've grouped them by configuration groups. For further configuration, see the section of this tutorial dealing with the processes you want to use.
* Under the **processing** configuration group
    * fill out absolute paths for the **DNG_Converter**, **SmartSelectDroplet**, and **FuzzySelectDroplet** if you intend to use them. Some exe files for the droplets have been included under utils, but since they are compiled for Windows they may not work for you. If not, see the below Appendix on masking for some tips and tricks for making your own. All paths should be in quotes, and should either have the backslashes escaped or use unix-style paths. Python doesn't care when it comes to pulling directories out of json files.
    * When a droplet is exported in photoshop, it has to have a hardcoded place to put the files when it's done with them. **Droplet_Output** is this directory, which should default to "C:\\tempmasks" The script will look for each mask in this directory as it is made and then move it elsewhere.
    * **Source_Type** and **Destination_Type** are respectively the type of the files which go into the pipeline and the files that should be used to build the model. If you have a Canon camera, Source_Type should be ".cr2" and Destination_Type should be ".jpg" if you wish to build your model from jpgs, ".tif" if you want to build from Tif files (slower) Note that **Destination_Type** is the type of files from which you want to build your model. Remember to include the '.'.
* Under the **photogrammetry** config group
   * All the detaults should be fine here.
   * mask_ext should be whatever filetype you exported the mask as. The default is ".png", which is what the included droplets export to. If you are instead using the CV2 masking options, you should change this to whatever you set under **Processing->CV2_Export_Type**. Be sure to include the "." in both.

## Notes on Masking
Happily, Agisoft Metashape now has an option to ignore stationary points when building a model, negating the need to do masking on many projects where the object is moving but the camera is not (ie. using a turntable). However, some projects still need to be masked because there are items in the scene moving with the target object that we do not want to include in our model like rulers, scale palettes, and cushions used to stabilize fragile objects. 
Objects are built using the "ignore stationary points" option by default, so with many projects, you can run the commands to [build an object from a folder of pictures](#i-already-have-raw-files-tif-files-or-jpg-files-and-i-want-to-build-a-3d-model-from-them) or from a manifest with the flag 
```
--maskoption 0
```
to build without masks. If you find you have unwanted objects in your scene, or if you are not getting good points on your model, you will need to mask. For that, this pipeling provides a couple of options, each of which require a little configuration.
### Masking with Photoshop or Other External Apps
Two photoshop droplets are provided in the util directory. One builds a mask using Photoshop 2024+'s context aware select tool, and the other uses the Magic Wand tool that has been in photoshop since forever. Both take the value of the center pixel in an image that is (5616x3744) and assume that it is on the desired object.  These are both accurate ways to mask models, with SmartSelect/Context Aware Select being the most accurate <ins>provided that the object you want to build a model of is on the center pixel is centered every picture.</ins> Unfortunately, photoshop droplets are really limited in their configurability. They don't allow you to specify which pixel to sample, for example, or the dimensions of your images. Furthermore, the included droplets may not work on your machine since they were exported on Windows 10. If you would like to use an external program like a droplet to generate a mask, it must meet several requirements:
* You must be able to run it from the command line with one parameter, a folder of files to mask.
* It must output to a directory that is NOT the directory you've configured under config.json->photogrammetry->mask_path. I've chosen a temp directory on c: that exists or could exist on almost all windows machines.

To configure the pipeline to use the new droplet: 

* In config.json->processing, change either **SmartSelectDroplet** or **FuzzySelectDroplet** to the path for your masking program or droplet.
* Change **Droplet_Output** to be the directory where your third party app saves the finished masks. Do not have the app save them to the directory configured in photogrammetry->mask_path. The code will copy the files from this directory to the mask directory that you specify under config.json->photogrammetry->mask_path.
* If you are planning on using a listener to wait for image files from a device or another computer, you will need to specify your droplet as the default masking option. Put the name of the config variable you changed to contain the path of your 3rd party app under **ListenerDefaultMasking**.

To use this method to build a model, specify --maskoption 1 or 2 on any command that takes this option, depending on whether you replaced SmartSelectDroplet (1) or FuzzySelectDroplet (2) with your own app.

### Masking using Grayscale Thresholding
This masking method builds a mask by converting each image to grayscale, and taking all pixels with RGB values above a particular threshold (closer to white) and turning them black, and all pixels with RGB values below that threshold (closer to black) and turning them white. To use it, you will need to configure a threshold. This is currently the fastest method and produces results that are as good as the magic wand select droplet.
* processing->**thresholding_lower_gray_threshold** should be be between 0 and 255 with 255 being white, and 0 being black.
* processing->**CV2_Export_Type** and photogrammetry->**mask_ext** ought to have the same value. The default is ".png". **CV2_Export_Type** is the image format that your masks will be saved to.
* If you are wanting to build masks as images come in from another computer to save time, **ListenerDefaultMasking** should be set to "Thresholding".

To use this method to build a model, specify --maskoption 4 on any command that takes this option.

### Masking using Edge Detection
This masking method uses Canny Edge Detection to detect edges in the image, selects the longest one, and fills it. Canny edge detection uses two thresholds because of the way it decides which edges to use in the final project. These need to be configured in config.json.
For more on Canny edge detection see: [OpenCV Docs on Canny Edge Detection](https://docs.opencv.org/3.4/da/d22/tutorial_py_canny.html)
* processing->**canny_lower_intensity_threshold** is a value between 1 and 200 representing intensity where the intensity corresponds to the gradient in the area. Below this intensity value, an pixel will not be considered part of the object of interest.
* processing->**canny_upper_intensity_threshold** is a value between 1 and 200 representing intensity. Above this value, a pixel will definitely be included in a curve representing an edge. Between these thresholds, a pixel will be included if it is connected to a pixel that is above the upper intensity threshold.
* processing->**CV2_Export_Type** and photogrammetry->**mask_ext** ought to have the same value. The default is ".png". **CV2_Export_Type** is the image format that your masks will be saved to.
* If you are wanting to build masks as images come in from another computer to save time, **ListenerDefaultMasking** should be set to "EdgeDetection".

To use this method to build a model, specify --maskoption 4 on any command that takes this option.

## Making Palettes
In order to automatically center, scale, and orient models we use a palette, which is a physical overlay placed on top of the turntable and underneath the object. These consist of computer readable targets encoding a number which will be the name of the target when read by Metashape. On the palette, these targets are placed relative to each other in an orientation which can be used to derive an X and Z axis in a world where the Y axis is up.
You can make and define your own palette, or you can print off the one we have included which is already defined. Either way, you'll find pallette definitions in the file **util/MarkerPalettes.json**, where you will also find the PDF files containing the palettes themselves. The palette itself can be printed from the file util/"Turntable targets (sheet size is 25 x 25 in).pdf" It ought to be printed at 25 x25 in to correspond to the large_axes_palette defined in MarkerPalettes.json

If you scale it differently, you will have to add a new entry to  MarkerPalettes.json or adjust the values already there. 
To add a Palette to the MarkerPalettes.json file, paste the following and modify the values:
 ```
        "my_palette":{
            "type":"12bit",
            "scalebars":{
                "type":"sequential",
                "labelinterval":1,
                "distance":2.0,
                "units":"cm"
            },
            "axes":{
                "xpos":[],
                "xneg":[],
                "zpos":[],
                "zneg":[]
            }
```
* All Units ought to be in metric, either mm, cm, or m. The unit on the top level ought to be the same as that specified for the scalebars. It will be used to name the output OBJ file so the user knows what units it uses by looking at the filename.
* "type" refers to the type of marker used on the palette. Your options here are Circular, 12bit, 14bit, 16bit, 20bit, Cross.
* "Scalebars" can either be determined from any two markers that are sequential in number ("type":"sequential") or explicitly defined ("type":"explicit").
   * If you have explicitly defined scalebars they need to be defined in an array "bars":[] where each bar is a JSON object with:
      *  "points" (a two member array of marker numbers)
      *  "distance", an integer specifying the distance between the points, and
      *  "units", which are the units of that distance in mm, cm, or m
```
 "scalebars":{
                "type":"explicit",
                "bars":[
                 {
                  "points":[1,2],
                  "distance":5,
                  "units":"cm"
                 },
                ]
```
   * If you wish to just find two sequential points and give a measurement between them, you can specify "type":"sequential". You need to specify the following properties on the scalebar object
      * "labelinterval"  is the numerical interval between two adjacent marker labels. ie, if you want to make a scalebar with point 61 and point 63, this value ought to be "2".
     * "distance" The distance between any two labels.
     * "units" the units of that distance in mm,cm, or m.
Finally, if you want to orient the object in space, you should specify which labels should be considered part of which axis. This is defined with an "axes" json object, which contains arrays corresponding to the positive and negative sides of the x and z axes. The arrays should contain integers corresponding to the numbers encoded by the targets on your palette, which also become the marker labels when the palettes get scanned by Metashape.


## Cookbook
Below are several "recipes" for using these scripts. Pick the tutorial for the task you want to complete.

### I already have RAW files, TIF files, or JPG files and I want to build a 3D Model from them.
Before you start, you will want to open config.json and adjust some settings for your model.
* Under Processing, make sure **Source_Type** and **Destination_Type** are set as described above. Remember that **Source_Type** is the type of image you have and **Destination_Type** is the type of image you want to build your model with.
* You will also want to fill out the pertinent values for the type of masking you'll be using. See the above section on **Notes on Masking.**
* Under Photogrammetry, the following values can be left at their defaults, but you should know what they do.
   * **sparse_cloud_quality** Corresponds with the quality of the sparse cloud in metashape when you run align photos. Must be 0,1,2,4, or 8 with 0 being the highest quality. If you are working with a small object and are not getting good results, you may want to set this to 0.
   * **model_quality** Corresponds with the quality of the model when building the model in metashape. Must be 1,2,4,8 or 16 with 1 being the highest quality.
   * **mask_path** Subdirectory of the project directory where masks will be stored. By default, it is ./masks in the project directory.
   * **output_path** where the model will be exported when built. By default it is ./output in the project directory.
   * **mask_ext** this is the type of file that the script will look for in the masks directory when importing masks into Metashape. Default is .png, but it should be configured to be the same value as you are outputing under **processing->CV2_Export_Type**
   * **error_thresholds** These values are used in the camera calibration process. Each point as a certain amount of error associated with its position.  The oprimization and error reduction process removes points with error above certain thresholds and recalibrates the cameras based on the points with less error. You may find that with skinny or small models you are getting holes in your model with these settings. If this is the case, you can raise projection accuracy to 6 or reconstruction uncertainty to more towards 30 until you get the results you want. Probably best to leave the rest alone.
   * **texture_size** The size of the texture to export. Should be a power of 2. 4096 is the default.
   * **texture_count** how many textures to export. You can divide the texture up into several large image files if you have a large object or want a very high resolution texture.
* The following values ought to be filled out by you
   *  **export_as** format to export. Should be obj or ply. You can also specify "all" and it will export both obj and ply. Note that right now, if you want to use Blender to take automated snapshots of the object, .obj works better than .ply.
   *  **palette** specify which palette you are using. If you don't know what that is, read the section entitled [Making Palettes](#making-palettes). Possible pallettes are, by default "small_axes_palette" and "large_axes_palette".


Now, to generate your model, you will use the following command, run from the museumcode directory with your virtual environment activated:
```
python photogrammetryScripts.py [Name of the Project] [Absolute Path to your folder of pictures] [Absolute Path to the project] --maskoption [1,2,3,4]
```
Masking options are as follows (which you will also see if you type "help" for this command). The default if you pass nothing at all is "No Masks." You should see the [Notes on Masking](#notes-on-masking) section above to pick which one works best for you, and for instructions on how to best configure it.

   0. No masks
   1. Photoshop droplet(context aware select)
   2. Photoshop droplet (magic wand),
   3. Canny Edge detection algorithm 
   4. Grayscale Thresholding"

For example: 
```
python photogrammetryScripts.py photogrammetry E29180 E:\automation\E29180\processed E:\automation\E29180 --maskoption 0

```

Here, I'm building a project called **E29180**, with the pictures in the directory **E:\automation\E29180\processed**, and I'm putting all intermediate files and products in the directory **E:\automation\E29180**. I'm using masking option 1, which is **No Masks**. 
You should then see a stream of output as masks are generated (if you chose to generate them) and as the model is built. The final obj or ply files will be placed in the ./output subdirectory of your project directory, or whatever you chose as the output directory in config.json.

#### Masking

This code facilitates the use of a seperate scanning workstation and photogrammetry workstation. It is meant to automate the workflow between the two.
### Configuration
- **ortery:pics_per_revolution** The ortery does not allow you to configure the number of degrees at which the pictures are taken on a per-camera basis. Therefore, we are pruning the number of pictures after.
In Config.json, under "Ortery", set the "pics_per_revolution" to the number of pictures you set the ortery to take per camera. For every 15 degrees, it's 24.
- **ortery:pics_per_cam** For each camera, set the number of pics that you want to keep for that camera. So, say you want to take a pciture every 30 degrees for the top camera, you would set cameras 5,6 to 12. Note that if you are going by degrees, you are limited to multiples of the degrees that you set for the number of pics per revolution, ie. 15 for a number of 24. For example, if you want to prune camera 5 down to 7 pics per revolution, this is not the same as getting a picture every 51 degrees on camera 5, but getting rid of 17 of 24 pictures taken at intervals of 15 degrees. The other thing to note, is that the camera numbers go from bottom to top (1-5) and from top to bottom(6-10), where you are doing a model in two hemispheres. If you don't like this, you can rename the cameras To prune pictures like this, run the transfer command with the --p flag.
- **transfer:networkdrive** Other useful configurations for the transfer include the transfer:networkdrive config value, which is the network drive the pics need to be transfered to. Right now, it will move all cr2 pics to this drive. If you are doing a windows directory, backslashes ought to be escaped with another backslash, or else enter it like you would a unix directory and let python sort out which is which.

```
usage: photogrammetryScripts transfer [-h] [--p] jobname imagedirectory

positional arguments:
  jobname         The name of this job. This translates into a subfolder on the network drive.
  imagedirectory  Copies images from this directory to the shared network folder as specified in config.json

options:
  -h, --help      show this help message and exit
  --p             Prunes every Nth file from Camera X, as specified in the config.json.
```

## Converters:
### Configuration:
Install Adobe's DNG converter( see above), and configure the path for it.
- **processing:DNG_Converter** This is the path to the DNG converter exec. If you are using windows, either escape the backslashes or type it like you would a unix path and let python sort it out.
  
To convert a folder of images from RAW to another type, run the following command, where the destination format is specified with a flag.
```
python photogrammetryScripts.py convert --dng ./samples/raw ./samples/dng
```
Here's the spec:
```
usage: convert [-h] [--dng] [--tif] imagedirectory outputdirectory

positional arguments:
  imagedirectory   Directory of raw files to operate on.
  outputdirectory  Directory to put the output processed files.

options:
  -h, --help       show  help message and exit
  --dng            Converts RAW to dng type
  --tif            Converts RAW to tif type
```
## Watcher
The watcher script is intended to be run on a computer which waits for pictures to show up in a folder and then builds models with them. It just runs in the background on that computer and waits for a manifest file entitled "Files_to_Process.txt" to appear in the directory specified in the config.json or on the command line. When the file appears, it makes a project directory in the configurable location, exports the RAW files to Tiffs, and builds a model.

### Configuration
- **listen_directory** This is the full path to the directory where the watcher should be listening for the manifest. Give a unix or Windows style directory, but if you use a Windows directory, escape the backslashes. If the user inputs a directory on the command line, the command line option will override this configuration.
- **project_base** the base directory which contains your model projects. Each new model project will be built out in this directory/projectname

```
usage: photogrammetryScripts watch [-h] inputdir

positional arguments:
  inputdir    Optional input directory to watch. The watcher will watch config:watcher:listen_directory by default.

options:
  -h, --help  show this help message and exit
```
## Photogrammetry
This function takes an input folder full of pictures in CR2 (NEF will probably be supported at some point) format and uses it to build a 3D model with Agisoft Metashape. It converts the files to TIF if needed and builds masks for each file. Then it adds them to one chunk in Metashape and builds a sparse cloud. It deletes potentially erroneous points, then uses the sparse cloud to create depth maps and a model. If scalebars are configured, markers are detected and scalebars are created with the configured values. If a marker pallette indicating x and z axes is used, the model is rotated such that the x and z and y on the pallette correspond with the world coordinate system. The model is centered on the origin in world space and scaled x1000 as all measurements in Metashape are in meters, whereas most objects that we are dealing with ought to be in mm. In the future, this scaling should be configurable.
The model is then exported in the specified format to the output folder created in the proejct directory passed in on the command line.

### Configuration
 - **sparse_cloud_quality** Corresponds with the quality of the sparse cloud in metashape when you run align photos. Must be 0,1,2,4, or 8 with 1 being the highest quality.
 - **model_quality** Corresponds with the quality of the model when building the model in metashape. Must be 1,2,4,8 or 16 with one being the highest quality.
 - **mask_path** Subdirectory of the project directory where masks will be stored. 

- **error_thresholds** Each point as a certain amount of error associated with its position. The oprimization and error reduction process removes points with error above certain thresholds and recalibrates the cameras based on the points with less error. You may find that with skinny or small models you are getting holes in your model with these settings. If this is the case, you can raise projection accuracy to 6 or reconstruction uncertainty to more towards 30 until you get the results you want. Probably best to leave the rest alone.
                "reconstruction_uncertainty":15,
                "projection_accuracy":5,
                "reprojection_error":0.3,
                "reprojection_max_selection_per_iteration":0.1,
                "reprojection_max_selection":0.5,
                "projection_accuracy_max_selection":0.5,
                "reconstruction_uncertainty_max_selection":0.5
- **texture_size** The size of the texture to export. Should be a power of 2. 4096 is the default.
- **texture_count** how many textures to export. You can divide the texture up into several large image files if you have a large object or want a very high resolution texture.
- **export_as** format to export. Should be obj or ply.
- **palette** The name of the marker palette you are using. This will act as a key to the configuration of the marker palette, which is loacted in util/MarkerPalettes.json

```
usage: photogrammetryScripts photogrammetry [-h] [--nomasks] jobname photos outputdirectory

positional arguments:
  jobname          The name of the project
  photos           Place where the photos in tiff or jpeg format are stored.
  outputdirectory  Where the intermediary files for building the model and the ultimate model will be stored.

options:
  -h, --help       show this help message and exit
  --nomasks        Skip the mask generation step.
```

