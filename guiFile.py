import json
import tkinter as tk 
import tkinter.ttk as ttk 
import mainFile 
import os 

CUR_DIR = os.path.dirname(os.path.abspath(__file__))

FOLDERS = [
    "Destination_Folder",
    "Source_Folder"
]

DICT_KEY_TO_STRING = {
    "Destination_Folder" : "Current Destination Folder : ",
    "Source_Folder" : "Current Source Folder : "
}

options = dict()
"""
If the settingsFile.json doesn't exists in the current folder, 
we create a new settingsFile.json with default settings 
"""

if (not os.path.isfile(CUR_DIR + r"\settingsFile.json")) :

    f = open(CUR_DIR + r"\settingsFile.json", "w")
    toWrite = dict()

    for e in FOLDERS : 
        toWrite[e] = os.path.dirname(os.path.abspath(__file__)) + "\\" + e

    json.dump(toWrite, f)
    f.close()



with open(CUR_DIR + r"\settingsFile.json", "r") as f : 
    options = json.load(f)

for e in FOLDERS : 

    if (not os.path.isdir(options[e])) :
        defaultFolder = os.path.dirname(os.path.abspath(__file__)) + "\\" + e 
        # If the folder for source files is not correctly formed, create a default folder 

        if (not os.path.isdir(defaultFolder)) : 
            # If the folder doesn't exists, create it 
            os.mkdir(defaultFolder)

        options[e] = defaultFolder

options["Current_Folder"] = os.path.dirname(os.path.abspath(__file__))
    
fw = open(CUR_DIR + r"\settingsFile.json", "w")
json.dump(options, fw)
fw.close()


def registerValue(ent, val) :

    def tempFunc() :
        res = ent.get()
        d = dict()

        with open(CUR_DIR + r"\settingsFile.json", "r" ) as f : 
            d = json.load(f)
            if (os.path.isdir(res) or True) : 
                d[val] = res 

        f = open(CUR_DIR + r"\settingsFile.json", "w")
        json.dump(d, f)
        f.close()

    return tempFunc

window = tk.Tk()

options = None 
with open(CUR_DIR + r"\settingsFile.json", "r") as f : 
    options = json.load(f)

lbl_destFolder = tk.Label(
    master = window, 
    text = DICT_KEY_TO_STRING["Destination_Folder"],
    width = len(DICT_KEY_TO_STRING["Destination_Folder"]) - 1,
    height=2,
    justify="right",
    anchor="e"
)

ent_destFolder = tk.Entry(
    master = window,
    width=100
)

ent_destFolder.insert(0, options["Destination_Folder"])
lbl_destFolder.grid(row=0, column=0)
ent_destFolder.grid(row=0, column=1)

lbl_srcFolder = tk.Label(
    master = window, 
    text = DICT_KEY_TO_STRING["Source_Folder"],
    width = len(DICT_KEY_TO_STRING["Destination_Folder"]) - 1,
    height=2,
    justify="right",
    anchor="e",
)

ent_srcFolder = tk.Entry(
    master = window,
    width=100,
) 

ent_srcFolder.insert(0, options["Source_Folder"])
lbl_srcFolder.grid(row=1, column=0)
ent_srcFolder.grid(row=1, column=1)

def updateLabels() :

    ent_destFolder.delete(0, tk.END)
    ent_srcFolder.delete(0, tk.END)

    values = None
    with open(CUR_DIR + r"\settingsFile.json", "r") as f :
        values = json.load(f)

    ent_destFolder.insert(0, values["Destination_Folder"])
    ent_srcFolder.insert(0, values["Source_Folder"])

def cmdForAccept() :
    registerValue(ent_srcFolder, "Source_Folder")()
    registerValue(ent_destFolder, "Destination_Folder")()
    updateLabels()
    return 

def cmdForReset() :

    toWrite = dict()

    for e in FOLDERS : 
        defaultFolder = os.path.dirname(os.path.abspath(__file__)) + "\\" + e 
        toWrite[e] = defaultFolder

    toWrite["Current_Folder"] = os.path.dirname(os.path.abspath(__file__))
        
    fw = open(CUR_DIR + r"\settingsFile.json", "w")
    json.dump(options, fw)
    fw.close()
    updateLabels()
    

btn_accept = tk.Button(
    text="Enregistrer",
    height=2,
    command=cmdForAccept
)

btn_reset = tk.Button(
    text="Réinitialiser",
    height=2,
    command=cmdForReset
)




btn_accept.grid(row=2, column=0)
btn_reset.grid(row=3, column=0)

window.mainloop()