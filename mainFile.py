from enum import Enum
import json 
import os 
import sys
import importlib.util
import subprocess
import FilterTypes 

CUR_DIR = os.path.dirname(os.path.abspath(__file__))

# Maximum number of files processed for each call 
NUMBER_FILES_PER_CALL = 20 


def launchProcessOneFilter(
        processMode : Enum, 
        classFilter
) :
    
    ordonnance = dict()

    with open(CUR_DIR + r"\settingsFile.json", "r") as f :
        optionsFile = json.load(f)
        ordonnance["Destination_Folder"] = optionsFile["Destination_Folder"] 
        ordonnance["Source_Folder"] = optionsFile["Source_Folder"]
        ordonnance["Current_Folder"] = optionsFile["Current_Folder"]

    ordonnance["processMode"] = processMode

    ordonnance["filter"] = classFilter.toDict()

    fileList = os.listdir(ordonnance["Source_Folder"])
    i = 0 
    filesToProcess = fileList[i:i+NUMBER_FILES_PER_CALL]


    nomProcedureSplitted = classFilter.name.split(":")
    ordonnance["Destination_Folder"] = ordonnance["Destination_Folder"] + "\\" + nomProcedureSplitted[0] + "_" + nomProcedureSplitted[1]

    if (not os.path.exists(ordonnance["Destination_Folder"])) :
        try:
            os.mkdir(ordonnance["Destination_Folder"])
            print(f"Directory '{ordonnance["Destination_Folder"]}' created successfully.")
        except FileExistsError:
            print(f"Directory '{ordonnance["Destination_Folder"]}' already exists.")
        except PermissionError:
            print(f"Permission denied: Unable to create '{ordonnance["Destination_Folder"]}'.")
        except Exception as e:
            print(f"An error occurred: {e}")

    jsonFilePath = ordonnance["Current_Folder"] + r"\temp\processData.json"

    while len(filesToProcess) > 0 : 
        ordonnance["fileList"] = filesToProcess
        
        with open(jsonFilePath, "w") as f : 
            json.dump(ordonnance, f)

        cmd = "gimp -ifs --quit --batch-interpreter=python-fu-eval -b \""
        cmd += "CUR_DIR = r\'" + CUR_DIR + "\';"
        cmd += "jsonFilePath = r'" + jsonFilePath + "\';"
        cmd += "exec(open(r'FileProcessor.py').read());"
        cmd += "\" "
        for fileName in filesToProcess : 
            cmd += ordonnance["Source_Folder"] + "\\" + fileName + " "
        print(cmd)
        #subprocess.run(cmd, shell=True)
        i += NUMBER_FILES_PER_CALL
        filesToProcess = fileList[i:i+NUMBER_FILES_PER_CALL]
    
    return True 


if __name__ == "__main__" : 

    procedureList = None 

    procedureJson = CUR_DIR + r"\listeProcedures.json"

    with open(procedureJson) as f : 
        procedureList = json.load(f)

    # ==============================================
    # The processing mode : RANDOM = 1, DEFAULT = 2 
    processMode = 1
    # ==============================================

    for procedure in procedureList :

        # We get the filter class from the dictionnairy 
        filterClass = FilterTypes.convertDictToFilter(procedure)

        launchProcessOneFilter(processMode, filterClass)