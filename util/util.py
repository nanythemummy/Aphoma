from sys import platform

def getConfigForPlatform(config):
    #In the json config, differing options for platform should folllow the format:
    #optionname:{
    #platformname:platformval
    #}
    #where possible platforms are Mac, Win, Linux.
    #The dictionary passed in here ought to be "optionname"
    if platform.startswith("linux"):
        return(config["Linux"])
    elif platform == "darwin":
        return(config["Mac"])
    else:
        return(config["Win"])