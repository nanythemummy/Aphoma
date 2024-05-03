# museumcode
Experimental  Scripts for use in a Museum or Archaeology
## Setup:
1. Install Adobe DNG Converter. You can find it here: https://helpx.adobe.com/camera-raw/digital-negative.html, if you want to use the DNG conversion command.
2. Setup a virtual environment:
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
4.  Install requirements.txt
  ```
  pip install -r requirements.txt
```

## Metashape
These scripts run metashape in headless mode via the python module. They require that the metashape wheel be manually installed and then activated with the product key. It is not in requirements.txt
Instructions can be found here:
https://agisoft.freshdesk.com/support/solutions/articles/31000148930-how-to-install-metashape-stand-alone-python-module
1. Download the Standalone Python Wheel from the metashape site. https://www.agisoft.com/downloads/installer/
2. ``` pip install c:\path\to\wheel\wheel.whl ```
3. Install the requirements text requirements as normal.

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
