# museumcode
Experimental  Scripts for use in a Museum or Archaeology
## Converters:
To convert a folder of images from RAW to another type, run the following command, where the destination format is specified with a flag.
```
python photogrammetryScripts.py convert --dng ./samples/raw ./samples/dng
```
### Requirements.
1. Adobe DNG Converter--you need to set an environment variable to tell the script where the converter is. See the file config.env for an example on MacOS.