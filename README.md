# museumcode
Experimental  Scripts for use in a Museum or Archaeology
## Setup:
1. Install Adobe DNG Converter. You can find it here: https://helpx.adobe.com/camera-raw/digital-negative.html
2. Setup a virtual environment:
  ```
  python3 -m venv venv
  source venv/bin/activate
  ```
3. DNG Converter needs to be an env variable. Find it on your computer and change the path in config.env
  ```
  source config.env
  ```

4.  Install requirements.txt
  ```
  pip install -r requirements.txt
  ```

## Converters:
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
### Requirements:
1. Adobe DNG Converter--you need to set an environment variable to tell the script where the converter is. See the file config.env for an example on MacOS.
2. If you are running on a mac, you can set your path with:
   ```
   source config.env
   ```
3. 
