# museumcode
Automated pipeline for building 3D Models with Photogrammetry, either using an ortery or pictures taken manually.
## Setup:
1. Install Adobe DNG Converter if you want to use the DNG conversion command.  You can find it on [Adobe's Camera Raw Page](https://helpx.adobe.com/camera-raw/digital-negative.html)
2. Setup a virtual environment
  UNIX
  ```
  python3 -m venv venv
  source venv/bin/activate
  ```
  WINDOWS
  ```
  python -m venv venv
  venv\scripts\activate.bat
  ```
3.  Install the dependencies in requirements.txt
  ```
  pip install -r requirements.txt
  ```
4.  Download and Install the Metashape standalone python module from the [Agisoft Download Page](httpw://www.agisoft.com/downloads) Note that you must have a license for metashape professional for this to work. Note that if you are using Python 3.12, as of 6/14/2024, they have not made the module explicitly compatible with it yet. It does in fact work. You just need to rename the file from Metashape-2.1.1-cp37.cp38.cp39.cp310.cp311-none-win_amd64 to Metashape-2.1.1-cp37.cp38.cp39.cp310.cp311.cp312-none-win_amd64
```
pip install Metashape-2.1.1-cp37.cp38.cp39.cp310.cp311.cp312-none-win_amd64
```

5. If you would like to build one mask for each photo using Photoshop's content aware masking, ensure that you have a copy of photoshop 2024 installed. If you have multiple versions of photoshop, you may want to open the latest because sometimes the droplet will open the wrong version and not the version it was made with. If you would not like to build makss this way, run the photogrammetry command with the --nomasks flag or choose one of the other masking options (TBA)

6. Make a copy of config_template.json and name it config.json. Change the values in it to suit the computer you are using and the job you want to do with it.

## Transfer
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

