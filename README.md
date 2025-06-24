# Aphoma Photogrammetry Asset Pipeline (UI and Command-line tools)

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
## Using the UI
Using the UI is much more straightforward than using the command line. You can start it at the moment by typing:
```
  python pipeline.py
```
![image](https://github.com/user-attachments/assets/fa5b19b8-eb44-4845-8ece-617b35bf438b)

1. To do a simple build, click the "Build" tab.
2. Name your project.
3. Use the browse button to navigate to the directory where you have stored your TIFs or JPGs that you want to build a model from.
4. Use the browse button where you want to store the projects.
5. In the dropdown, choose your masking method.
6. Choose the pallette that you would like to use for measurement.
7. Click Build.
8. To change configurations, click the configure button at the bottom to access the configuration screen. Change the required value and click "OK" at the bottom. Configuration will be reloaded automatically.

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



## Command Line Cookbook
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
   *  **palette** specify which palette you are using. If you don't know what that is, read the section entitled [Making Palettes](#making-palettes). Possible pallettes are, by default "small_axes_palette" and "large_axes_palette". If you don't want to use one at all, delete this attribute in your config.json file or type "None".
   *  **custom_face_count** If you want to build a very high resolution model for archival purposes, set this to 0. This will cause Metashape to build a model with the max number of polygons that your photographs will support. The number you provide here will be used as the face count for the high resolution version of your model that gets exported. If you would like to go to the default, "high resolution" model, delete this key from the json object.
   *  **low_res_poly_count** This script will export a high resolution and decimated version of your model. The low resolution one is good for streaming over the internet, but may lose some detail when viewed without its texture. This is the target polygon count that your low-resolution model will be decimated to.


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

### I have an Ortery or a similar device, and I would like to build models on a second computer while photographing on the first
The basic strategy here is to run the sending script on the machine which is hooked up to your camera or Ortery while running the watcher script on the machine that you want to build your model. The building machine will make certain assumptions about how you want to do masking and do the filetype conversion and masking work while you are still taking pictures on your photography machine. Then, when you are will done, the photography machine will send a manifest of all the files in the model to the build machine and the build machine will use that to collect all the files for one model into one place and to build the model.
* You need to use Windows to set up a shared folder on your build machine that is accessible from both computers. To share the a folder on the build machine, see the following [instructions from the Microsoft webpage](https://support.microsoft.com/en-us/windows/file-sharing-over-a-network-in-windows-b58704b2-f53a-4b82-7bc1-80f9994725bf#ID0EBD=Windows_11).
* Then, you need to [mount that folder as a network drive on the photography computer](https://support.microsoft.com/en-us/windows/map-a-network-drive-in-windows-29ce55d1-34e3-a7e2-4801-131475f9557d). For the below examples, my folder e:\photogrammetry on the build computer is now x:\photogrammetry on the photography machine.
* At the moment, SCP and other file transfer protocols are not supported, though they may be in the future. If you would still like to use the watcher script to build models without a the send script, configure the listening script, then see the tutorial below for the situation where [I would like to send my images to another, faster machine to build.](#i_would_like_to_send_my_images_to_another_faster_machine_to_build).

#### Configuring and Running the Watcher Script

* Configure the Watcher in config.json
   * Under watcher->**listen_directory**, put the directory that you want the watcher to look for incoming image files on. You can also specify this as a positional argument on the command line.
   * watcher->**temp_scratch** Specify a directory where the watcher can temporarily store its work products (converted files and masks) while it waits for a manifest from the photography computer.
   * watcher->**project_base** is the base directory in which all model projects will be stored. When the model is finished, your model will be in project_base\\my_project_name
 * Run the watcher script
```
python photogrammetryScripts.py watch
\\likewise, if you did not want to configure the directory to listen on, you can specify it with the --inputdir optional argument.
python photogrammetryScripts.py watch --inputdir "e:\photogrammetry"
```
The script will loop in the background waiting for files to arrive. If you want to exit it, type **F**

#### Configuring and running the Listen-Send Script
* On the machine connected to the ortery, configure the following in config.json
   * watcher->**listen_and_send** should be the directory where your third party photography device uploads the photographs to your computer. For example, while it is in the process of taking photos, the Ortery Capture software will store JPGs and RAW files in C:\%USERPROFILE%\Pictures\Ortery\~temp
   * watcher->**networkdrive** should be the networkdrive that you mapped above, for example: "x:\photogrammetry". This is where the files from the ortery will be sent for the watcher script to pick them up.\
* If you are taking pictures with a multi-camera machine, you may find that the machine takes more pictures than you want at certain angles and it is not tunable from within the Ortery (or other) software. The following configuration allows you to remove every Nth picture on a specified camera. It counts pictures based on the temporary numbering that the Ortery gives them and in this way is very Ortery specific. You can configure your ortery setup if you are using one as follows in the ortery object in config.json.
   * ortery->**pics_per_revolution**. This is the number of pictures taken by a single camera during a 360 rotation of the ortery turntable.
   * ortery->**pics_per_cam**. This attribute contains a dictionary mapping camera numbers to the desired number of pictures to be sent to the build machine from each camera. The following is an example of a configuration for an ortery taking a picture of a pot on a turntable where the pot must be photographed right-side-up and then again upside-down. Cameras 1-5 are the lowest to highest angle cameras respectively on the first (rightside up) pass, and cameras 6-10 are the lowest to highest angle cameras on the second (upside-down) pass. The cameras at the highest angles (4,5,9,and 10) are set to take fewer pictures, because at this angle, pretty much every picture has a high overlap of information when compared to the last. Furthermore, it is assumed that pretty much all the information in picture 6 will be overlapped in the previous pictures, so the number of desired pictures for it is set to 12 meaning that the sender script will only send 12 of the 24 pics taken. For the best results, the pics_per_cam ought to divide evenly into pics_per_revolution.
     ```
         "ortery":
        {
            "pics_per_revolution":24,
            "pics_per_cam":{"1":24,
                            "2":24,
                            "3":24,
                            "4":6,
                            "5":6,
                            "6":12,
                            "7":24,
                            "8":24,
                            "9":6,
                            "10":6}
        }
     ```
    Now you are all configured, you should run the listen-send script with the following command.
  ```
  python photogrammetryScripts.py listenandsend ProjectName
  ```
  You can also specify the following arguments:
  * --inputdir is the directory to look for incoming files in--if you don't specify it, the directory gets pulled from watcher->**listen_and_send**
  * --maskoption [1,2,3,4] This is not usually useful in this usecase. If you are for some reason not using the watcher script, this will specify the masking option in the manifest that gest sent at the end of the job so that you can run the build later at your leasure with a custom masking option. Normally, the build comptuer is masking while you are photographing, and there is no way to tell it that you should use one masking method over the other, so the watcher computer will use the default masking method specified in configuration under processing->**ListenerDefaultMasking** For information on what the options do, see the [section on masking options](#notes_on_masking)
  * --prune This will run the pruning script that selects a subset of pictures to send to the build computer based on the filename of the picture and the configuration values specified in the config.json ortery object.

    When you are finished photographing a single object, type **F** to send the manifest to the build comptuer.

### I would like to send my images to another, faster machine to build.
TBD
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

