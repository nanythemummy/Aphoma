# Multibanded Boards Command-Line Script

Multibanded Boards takes a folder of multibanded photographs of an object and builds orthomosaics for them. These are all the same size and can be overlaid in photoshop to highlight areas that flouresce on the orthomosaic made from normal Visible Light photographs.

## Assumptions

Multibanded boards expects the following to function properly:
- An input folder where all of the files are in the input folder, and not in subdirectories. It's not recursive.
- All files must have the name `<Object Name>_<front_or_back><band><photo number 000>.jpg` For example, A3697_31760.95_BackIrIr007.jpg
- Possible bands are IrIr, VisVis, VisIr, UvUv, and UvVis, where UvVis is visible light stimulated UV, etc.
- You can see and (carefully) change the possible bands in config.json and config_template.json under `multibanded:{}`
- Also, note `pointcloud_reference` under `multibanded:{}`. This is a dependency. It means that if a band has a `pointcloud_reference` that is another band, that band a) must have images in your image folder and b) the images for that band must have been taken in the same place as the images in the referring band. for example: 
```
    "multibanded":{
            "uvuv":{
                        "desc":"Reflected Ultraviolet",
                        "path":"uvuv",
                        "pointcloud_reference":"uvvis",
                        "grayscale_ortho":"True",
                        "eightbit":"True",
                        "graychannel":"b",
                        "brightness":1.9
    },
}
```
   In this configuration, the band UvUv depends on the band UvVis. Picture 001 of UvUv was taken in the same physical location Picture 001 of UvVis, and is stored in the same folder. This is because UvUv does not usually have as much information to build a model as UvVis, so the photos for UvVis are used to build the point cloud for UvUv, and the the UvUv photos are substituted in to build the orthomosaic.

- Finally, you should place CHI scalebars with the following numbered markers in the following configuration.
```
        16=========15
        -----------------
 4      |               |
 ||     |               |
 ||     |               |
 ||     |               |
 5      |    Object     |
 ||     |               |
 ||     |               |
 ||     |               |
 6      |               |
        -----------------
        8============7
```
* If you don't have CHI scalebars, you can configure your own scalebars in [MarkerPalettes.json](util/MarkerPalettes.json)

    * Under `multibanded:{` in MarkerPalettes.json, look for 
    ```
     "bars":[
                {
                "points":[5,6],
                "distance":250.07,
                "units":"mm"
                },
    ```
    Change the values under points to be pairs from the scalebars that you have where the numbers correspond to the number of the target. Then enter the measurements between those two points in mm.
    * Pick one set of Points which will be the X-Axis for your model and enter those points under `xaxis`. In the below example (and the diagram above), the points are targets number 4, and 6.
        ```     
        "xaxis":[4,6],
        ```
    * Then, pick points which will reliably be in a plane--ie, they are lying on the same flat surface your object is. Put those in the `plane` value. In the example below and the diagram above, Points 7,8,15,and 16 are always guaranteed to be in a plane in our photography process.

        ```
            "plane":[7,8,15,16]
        ```



## Requirements:
* Python 3.12 (inference_sdk in requirements.txt is not yet compatible with higher versions)
* Agisoft Metashape (requirements.txt assumes you have 2.2.1 or higher)
* [Exiftool](https://exiftool.org) Unzip it somewhere you will be able to find it. Here, I've used c:\exiftool\exiftool.exe

## Installation Instructions
* Install [Python 3.12](https://www.python.org/downloads/) If you are on mac, you can get it via [Homebrew](https://formulae.brew.sh) via the command `brew install python@3.12`
* Clone this git repo. For this instruction set we will assume `c:\projects\aphoma` (or `~/projects/aphoma`) for simpliity.
* In the Aphoma directory, set up a virtualenv.

    PC:
    ``` cd c:\projects\aphoma
        py -3.12 -m venv venv
        venv\scripts\activate
    ```
    Mac:
    ``` 
        cd ~/projects/aphoma
        /opt/homebrew/opt/python@3.12/libexec/bin/python -m venv venv
        source venv/bin/activate
    ```
* Install the required libraries. If your network blocks the agisoft domain, you need to open the requirements.txt file and comment out (put a # in front of them) the lines starting with "Metashape @"
    
    PC and Mac
    ```
    pip install -r requirements.txt
    ```
* Install the metashape python api if you have to download it seperately
   
    PC and Mac
    ```
    pip install Metashape-2.2.1-cp37.cp38.cp39.cp310.cp311-abi3-win_amd64.whl
    ```
* Make a configuration file.

    PC
    ```
    copy config_template.json config.json
    ```

    Mac
    ```
    cp config_template.json config.json
    ```
 * Make sure the following values in config.json are correct for your computer: "ExifTool".
 For example, on a PC:

    ```   
     "config":
        {

            "processing":
            {
                ...
                "Exiftool":"c:\\exiftool\\exiftool.exe",
                ...
            }
        }
    ```
* If you would likethe build to fail if there are unaligned photos in any of the bands, set the config value `"photogrammetry":"fail_on_unaligned" ` to true.

## Running the script
To run the script, before you type the command, ensure your virtual environment is running. You should have `(venv)` before the directory in your command prompt. If it's not, run the activate script:

PC:
```venv\Scripts\activate```

Mac: ```source venv/bin/activate```

(To deactivate, you can always type `deactivate`)

Run the script with the following command on all OSes

```python multibanded_boards.py [directory with pictures] [base directory] [name of project]```

So, on my mac, if my folder of photos is ~/Projects/SG3/input, I can type:

```python multibanded_boards.py ~/Projects/SG3/input ~/Projects/SG3 SG3```

My final orthomosaics will be saved in
`~/Projects/SG3/output`.