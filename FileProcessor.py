import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gimp', '3.0')
from gi.repository import Gio 
from gi.repository import Gimp
from enum import Enum
import os 
import json 



# Allows for the import of a module even if it's not part of the pyton path 
# From : https://www.pythonmorsels.com/dynamically-importing-modules/
import sys
import importlib.util
def import_from_path(module_name, file_path):
    """Import a module given its name and file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

filterTypePath = ""

if (len(filterTypePath) == 0) :
    raise Exception("FilterType path has not been setup yet.")

FilterTypes = import_from_path("FilterTypes", filterTypePath)

class RunType (Enum) :
    RANDOM = 1
    DEFAULT = 2

def processOneFileOneFilter(
        fileIndex : int,
        processMode : Enum, 
        filesList : list[str],
        destFolder : str,
        Filter
) :
    
    # On charge la première image 
    image = Gimp.Image.get_by_id(fileIndex + 1)
    print(image== None)

    # On crée une layer qui est un calque de l'image 
    layer = Gimp.Layer.new_from_visible(
        image,
        image,
        "Copium"
    )
    
    # On crée un DrawableFilter, sur lequel on peut appliquer des filtres non-destructeur 
    gFilter = Gimp.DrawableFilter.new(
        layer, 
        Filter.name, 
        Filter.name
    )

    # Paramètres du filtre qui sont indépendant du filtre 
    gFilter.set_blend_mode(Gimp.LayerMode.REPLACE)
    gFilter.set_opacity(1.0)
    config = gFilter.get_config()

    # On initialise les paramètres du filtre 
    for p in Filter.parameters : 
        match processMode : 
            case RunType.RANDOM : 
                rVal = p.getRandomValue()
                config.set_property(p.name, rVal)
                print("Pour : " + p.name + " chosen value : " + str(rVal))

    # On met à jour le filtre 
    gFilter.update()

    if (not gFilter.is_valid()) :
        print('Filter not valid')

    # On applique le filtre à la layer 
    layer.append_filter(gFilter)

    toSave = Gio.file_new_for_path(destFolder + "\\" + filesList[fileIndex])

    print('The file exists : ' + str(toSave.query_exists(None)))

    # On ajoute le filtre à l'image 
    image.insert_layer(
        layer, 
        None,
        -1
    )

    # On a maintenant 2 layers, une layer avec le filtre appliqué, ainsi qu'une layer 
    # avec l'image initiale

    valide = Gimp.file_save(
        Gimp.RunMode.NONINTERACTIVE, 
        image, 
        toSave, 
        None
    )
    print('Sauvegarde confirmée : ' + str(valide))

    gFilter.delete()
    image.delete()

def processMultipleFilesOneFilter(
        filePath : str
) :
    processDetails = None 
    with open(filePath) as f :
        processDetails = json.load(f)

    if (processDetails == None) : 
        return False

    fileList = processDetails["fileList"]
    destFolder = processDetails["destFolder"]
    processMode = processDetails["processMode"]
    Filter = FilterTypes.convertDictToFilter(processDetails["filter"])
    
    for i in range(len(fileList)) :

        processOneFileOneFilter(
            i,
            processMode,
            fileList,
            destFolder,
            Filter
        )
    
    return 

processMultipleFilesOneFilter(jsonFilePath)

