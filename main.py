from enum import Enum
import json 

import sys
import importlib.util
def import_from_path(module_name, file_path):
    """Import a module given its name and file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

FilterTypes = import_from_path("FilterTypes", r"C:\Users\Andy\Documents\DossierLicence\Dossier_Master\pai2d-2026\FilterTypes.py")

# Maximum number of files processed for each call 
NUMBER_FILES_PER_CALL = 20 

data = None 
procedureJson = r"C:\Users\Andy\Documents\DossierLicence\Dossier_Master\pai2d-2026\listeProcedures.json"
with open(procedureJson) as f : 
    data = json.load(f)

def launchProcessOneFilter(
        folderPath : str,
        processMode : Enum,
        filter
) :
    ordonnance = dict()


    ordonnance["destFolder"] = folderPath