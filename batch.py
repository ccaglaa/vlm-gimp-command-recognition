#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Ce fichier montre comment appliquer un filtre sur une image 

# Éxécuter cette commande sur powershell pour obtenir une image :  
# gimp -nidfs --quit --batch-interpreter=python-fu-eval -b @"
# exec(open('batch.py').read())
# "@ <CHEMIN VERS L'IMAGE ORIGINALE>

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gio 
import sys

def changeOneImage() : 

    destination = ''

    if (destination.equals('')) :
        print('====== ATTENTION : LE CHEMIN DE DESTINATION N\'AS PAS ETE INITIALISE =====')
        return 
    
    image = Gimp.Image.get_by_id(1)
    new_image = Gimp.Image.new(
        image.get_width(),
        image.get_height(),
        image.get_base_type()
    )

    layer = Gimp.Layer.new_from_visible(
        image,
        image,
        "Copium"
    )
    

    # It needs to be a layer in order to be drawn over 
    filter = Gimp.DrawableFilter.new(
        layer, 
        'gegl:shift', 
        'Shift'
    )

    filter.set_blend_mode(Gimp.LayerMode.REPLACE)
    filter.set_opacity(1.0)
    config = filter.get_config()
    config.set_property('shift', 10)
    config.set_property('direction', 'vertical')
    config.set_property('seed', 399)


    filter.update()
    if (not filter.is_valid()) :
        print('Filter not valid')
    layer.append_filter(filter)


    toSave = Gio.file_new_for_path(destination)

    print('The file exists : ' + str(toSave.query_exists(None)))

    image.insert_layer(
        layer, 
        None,
        -1
    )

    valide = Gimp.file_save(
        Gimp.RunMode.NONINTERACTIVE, 
        image, 
        toSave, 
        None
    )
    print('Sauvegarde confirmée : ' + str(valide))

    filter.delete()
    image.delete()
    new_image.delete()

def procAlter2 () : 
    print('Where are the boots ?')

if __name__ == '__main__':
    # test1.py executed as script
    # do something
    procAlter()

