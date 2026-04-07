from enum import Enum
import json 
import os 
import sys
import importlib.util
import subprocess
def import_from_path(module_name, file_path):
    """Import a module given its name and file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# ==============================================
# Absolute path of the FilterType.py file 
filterTypePath = ""
# ==============================================


if (len(filterTypePath) == 0) :
    raise Exception("FilterType path has not been setup yet.")

FilterTypes = import_from_path("FilterTypes", filterTypePath)

# Maximum number of files processed for each call 
NUMBER_FILES_PER_CALL = 20 



def run(cmd):
    completed = subprocess.run(cmd, capture_output=True)
    return completed

def launchProcessOneFilter(
        jsonFilePath : str,
        originFolder : str, 
        folderPath : str,
        processMode : Enum,
        dFilter
) :
    ordonnance = dict()

    ordonnance["destFolder"] = folderPath
    ordonnance["processMode"] = processMode
    ordonnance["filter"] = dFilter.toDict()

    fileList = os.listdir(originFolder)
    i = 0 
    filesToProcess = fileList[i:i+NUMBER_FILES_PER_CALL]

    while len(filesToProcess) > 0 : 
        ordonnance["fileList"] = filesToProcess
        
        with open(jsonFilePath, "w") as f : 
            json.dump(ordonnance, f)

        cmd = "gimp -ifs --quit --batch-interpreter=python-fu-eval -b \""
        cmd += "jsonFilePath = r'" + jsonFilePath + "\';"
        cmd += "exec(open(r'FileProcessor.py').read());"
        cmd += "print(jsonFilePath);"
        cmd += "\" "
        for fileName in filesToProcess : 
            cmd += originFolder + "\\" + fileName + " "
        subprocess.run(cmd, shell=True)
        i += NUMBER_FILES_PER_CALL
        filesToProcess = fileList[i:i+NUMBER_FILES_PER_CALL]
    
    return 

data = None 

# ==============================================
# Absolute path of the json file containing the list of available procedures 
procedureJson = ""
# ==============================================

if (len(filterTypePath) == 0) :
    raise Exception("listeProcedure path has not been setup yet.")

with open(procedureJson) as f : 
    data = json.load(f)



# ==============================================
# Absolute path of the temporary json file that will contain the parameters for the GIMP part 
jsonFilePath = ""
# ==============================================

if (len(jsonFilePath) == 0) :
    raise Exception("jsonFilePath path has not been setup yet.")

# ==============================================
# Absolute path of the folder that contains the images to process 
originFolder = ""
# ==============================================

if (len(originFolder) == 0) :
    raise Exception("originFolder path has not been setup yet.")


# ==============================================
# Absolute path of the folder where you want your images to end up in 
folderPath = ""
# ==============================================

if(len(folderPath) == 0) :
    raise Exception("folderPath path has not been setup yet ")

# ==============================================
# The processing mode : RANDOM = 1, DEFAULT = 2 
processMode = 1
# ==============================================

# This example is for the first filter contained in the json file 
dFilter = FilterTypes.convertDictToFilter(data[0])

launchProcessOneFilter(jsonFilePath, originFolder, folderPath, processMode, dFilter)
