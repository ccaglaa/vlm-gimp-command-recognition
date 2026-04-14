import json
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as filedialog
from typing import List
import mainFile
import os

CUR_DIR = os.path.dirname(os.path.abspath(__file__))

FOLDERS = ["Destination_Folder", "Source_Folder"]

DICT_KEY_TO_STRING = {
    "Destination_Folder": "Current Destination Folder : ",
    "Source_Folder": "Current Source Folder : ",
}

SETTINGS_FILE = CUR_DIR + r"\settingsFile.json"


def setupFunc():
    """
    This function allows us to setup the settings file if it dosen't
    exist
    """

    options = dict()

    if not os.path.isfile(SETTINGS_FILE):

        f = open(SETTINGS_FILE, "w")
        toWrite = dict()

        for e in FOLDERS:
            toWrite[e] = os.path.dirname(os.path.abspath(__file__)) + "\\" + e

        json.dump(toWrite, f)
        f.close()

    with open(SETTINGS_FILE, "r") as f:
        options = json.load(f)

    for e in FOLDERS:

        if not os.path.isdir(options[e]):
            defaultFolder = os.path.dirname(os.path.abspath(__file__)) + "\\" + e
            # If the folder for source files is not correctly formed, create a default folder

            if not os.path.isdir(defaultFolder):
                # If the folder doesn't exists, create it
                os.mkdir(defaultFolder)

            options[e] = defaultFolder

    options["Current_Folder"] = os.path.dirname(os.path.abspath(__file__))

    fw = open(SETTINGS_FILE, "w")
    json.dump(options, fw)
    fw.close()


def updateSetting(ent: tk.Entry, key: str):
    """
    Updates the settings file with the input from
    the ent Widget
    """

    def tempFunc():

        settingsDict = None
        with open(SETTINGS_FILE, "r") as f:
            settingsDict = json.load(f)

        potentialNewDir = ent.get()

        if os.path.isdir(potentialNewDir):
            settingsDict[key] = ent.get()
            fw = open(SETTINGS_FILE, "w")
            json.dump(settingsDict, fw)
            fw.close()

    return tempFunc()



def selectFolder(ent: tk.Entry):
    """
    If called, will prompt the user to select a folder
    and then update the entry passed as a parameter with this folder path
    """

    def tempFunc():
        folderPath = filedialog.askdirectory(
            initialdir=CUR_DIR, title="Select a directory"
        )

        if len(folderPath) > 0:
            ent.delete(0, tk.END)
            ent.insert(0, folderPath)

    return tempFunc


if __name__ == "__main__":

    setupFunc()
    optionsInit = json.load(open(SETTINGS_FILE, "r"))

    window = tk.Tk()

    window.title("Folder Selection")

    # The row for the source folder

    lbl_sourceFolder = tk.Label(
        master=window,
        text=DICT_KEY_TO_STRING["Source_Folder"],
        width=24,
        height=2,
        anchor="e",
    )

    ent_sourceFolder = tk.Entry(master=window, width=65)

    ent_sourceFolder.insert(0, optionsInit["Source_Folder"])

    btn_sourceFolder = tk.Button(
        master=window,
        text="Select Folder",
        command=selectFolder(ent_sourceFolder),
        relief=tk.RIDGE,
        borderwidth=5,
    )

    lbl_sourceFolder.grid(row=0, column=0)
    ent_sourceFolder.grid(row=0, column=1)
    btn_sourceFolder.grid(row=0, column=2, padx=5)

    # The row for the destination folder

    lbl_destFolder = tk.Label(
        master=window,
        text=DICT_KEY_TO_STRING["Destination_Folder"],
        width=24,
        height=2,
        anchor="e",
    )
    ent_destFolder = tk.Entry(master=window, width=65)

    ent_destFolder.insert(0, optionsInit["Destination_Folder"])

    btn_destFolder = tk.Button(
        master=window,
        text="Select Folder",
        command=selectFolder(ent_destFolder),
        relief=tk.RIDGE,
        borderwidth=5,
    )

    lbl_destFolder.grid(row=1, column=0)
    ent_destFolder.grid(row=1, column=1)
    btn_destFolder.grid(row=1, column=2, padx=5)

    # Button to actually update the settings of the file
    # with the entries Widgets

    def updateAll():
        updateSetting(ent_sourceFolder, "Source_Folder")
        updateSetting(ent_destFolder, "Destination_Folder")

    btn_confirm = tk.Button(
        text="Confirm", command=updateAll, relief=tk.RIDGE, borderwidth=5
    )

    btn_confirm.grid(row=2, column=0, padx=5)

    def resetSettings() : 
        os.remove(SETTINGS_FILE)
        setupFunc()

        settingsDict = json.load(open(SETTINGS_FILE, "r"))

        ent_sourceFolder.delete(0, tk.END)
        ent_destFolder.delete(0, tk.END)

        ent_sourceFolder.insert(0, settingsDict["Source_Folder"])
        ent_destFolder.insert(0, settingsDict["Destination_Folder"])

    btn_reset = tk.Button(
        text="Reset Settings", command=resetSettings, relief=tk.RIDGE, borderwidth=5
    )

    btn_reset.grid(row=2, column=1, padx=5)

    window.mainloop()
