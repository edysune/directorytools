#searchDirectory.py

import json 
import os
import argparse

# 2) Compare 2 directories against each other
# 2.5  may need to look into GUI options? GUI options implies that we need a config file saved for this with reading/writing capabilities.

# 3) See about writing these types of things to a database

# 4) Create a GUI for this

# 5) Once in a database, should write some type of logic to merge into existing database

# 6) Should create logic around databases pulling information from database resource sites
# - Title Recommendations, Seasons, Episodes that do/don't exist, incomplete libraries, shows that are not found, bad structures of stuff

# 7) Possible additions to functionality like mass renaming of episodes and structures, update libraries logs, scan libraries for new data 

# 8) Possible subtitle downloading and merging? Not sure how useful this would be.


# Note: May need a way to group together similiar directories instead of just using absolute paths?
# Note: May need a tool for directory comparitors too - might be useful to have that as a top level tool before this

#============================= DEFINE DEFAULT AND GLOBAL VARIABLES =============================
# set and initialize variables used throughout the rest of the program
default_debugger = False
default_quieter = True
default_folderAnalyze = True
default_output_folder = 'output.json'
default_size = "KB"

globalSizeConversion = ""

#directoryToSearch1 = "../test_dir/a1";
#directoryOutputFile1 = "../output/a1.json";
#directoryToSearch2 = "../test_dir/a2";
#directoryOutputFile2 = "../output/a2.json";

#============================= DEFINE ARGPARSE =============================
# construct the argument parser
ap = argparse.ArgumentParser()
ap.add_argument("-p", "--path", help="Path to the root directory to start analysis - Program will recursively analyze path for files and folders.")
ap.add_argument("-f", "--folder", help="true/false or t/f supported. This argument analyzes folder structs as a whole, instead of individual files. This will run alongside the file program, and output to folder.<output.json>.")
ap.add_argument("-s", "--size", help="Conversion Size for file output. B, KB, MB, GB are supported currently. KB is set by default unless specified otherwise.")
ap.add_argument("-o", "--output", help="path and filename of output json file created. Defaults to output.json.")
ap.add_argument("-q", "--quiet", help="true/false or t/f supported. This argument quiets printing to the screen in a more readable tree-like structure aside from writing object to json.")
ap.add_argument("-d", "--debug", help="true/false or t/f supported. This argument turns debugging prints on/off, which gives slightly more information about program as it runs.")
args = vars(ap.parse_args())

#============================= DEFINE FUNCTIONS =============================
def parseAllArgs(args):
    # parse the arguments when program is used
    tdirectory = parseDirectory(args)
    toutput = parseOutputFile(args)
    tquieter = parseQuiet(args)
    tdebugger = parseDebug(args)
    tfolderAnalyze = parseFolder(args)
    tsize = parseSize(args)
    return tdirectory, toutput, tquieter, tdebugger, tfolderAnalyze, tsize

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing directory keys. At least 1 must be something other than None
#Returns:
#   tdirectory     a folder path. Program exits if it doesn't exist.
def parseDirectory(args):
    if args["path"] is None:
        print("-p <PATH SEARCH PATH> is not defined\nPlease see HELP screen for more information about how to use this program.")
        exit()
    tdirectory = args["path"]
    if not os.path.exists(tdirectory):
        print(f"Error: directory {tdirectory} does not exist - Please verify path")
        exit()
    return tdirectory

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing output keys. Is not a required field.
#Returns:
#   toutput     an output file name. Program uses default json output file if not defined
def parseOutputFile(args):
    if args["output"] is None:
        return default_output_folder
    return args["output"]

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing output keys. Is not a required field.
#Returns:
#   tdebug        a valid boolean value either True/False. If anything else is given, the value is reverted back to default
def parseDebug(args):
    if args["debug"] is None:
        return default_debugger

    tdebug = args["debug"].lower()
    if tdebug == "true" or tdebug == "t":
        return True
    elif tdebug == "false" or tdebug == "f":
        return False
    else:
        print(f"Error: debug argument {tdebug} not true/false or t/f - defaulting to {default_debugger}")
        return default_debugger


#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing quiet key that contains either true/t or false/f.
#Returns:
#   tquieter        a valid boolean value either True/False. If anything else is given, the value is reverted back to default
def parseQuiet(args):
    if args["quiet"] is None:
        return default_quieter

    tquieter = args["quiet"].lower()
    if tquieter == "true" or tquieter == "t":
        return True
    elif tquieter == "false" or tquieter == "f":
        return False
    else:
        print(f"Error: quieter argument {tquieter} not true/false or t/f - defaulting to {default_quieter}")
        return default_quieter


#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing quiet key that contains either true/t or false/f.
#Returns:
#   tfolderAnalyze        a valid boolean value either True/False. If anything else is given, the value is reverted back to default
def parseFolder(args):
    if args["folder"] is None:
        return default_folderAnalyze

    tfolderAnalyze = args["folder"].lower()
    if tfolderAnalyze == "true" or tfolderAnalyze == "t":
        return True
    elif tfolderAnalyze == "false" or tfolderAnalyze == "f":
        return False
    else:
        print(f"Error: folder argument {tfolderAnalyze} not true/false or t/f - defaulting to {default_folderAnalyze}")
        return default_folderAnalyze


#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing quiet key that contains B, KB, MB, or GB
#Returns:
#   tsize        a valid value for B, KB, MB, or GB. If anything else is given, the value is reverted back to default
def parseSize(args):
    if args["size"] is None:
        return default_size

    tsize = args["size"].lower()

    validValues = ["b", "kb", "mb", "gb"]

    if tsize in validValues:
        return tsize
    else:
        print(f"Error: size argument {tsize} not B, KB, MB, or GB - defaulting to {default_size}")
        return default_size


#============================= Public Functions =============================

def getSize(size, conversion):

    conversionRate = 1
    conversion = conversion.upper()

    if conversion == "B":
        return f'{size} {conversion}'

    # todo: refactor this, this is done horribly but shouldn't have much problems with simple data
    if conversion == "KB":
        conversionRate = 1000
    elif conversion == "MB":
        conversionRate = 1000000
    elif conversion == "GB":
        conversionRate = 1000000000

    return f'{size / conversionRate} {conversion}'

#============================= SUPPLEMENTAL CLASSES =============================

class fileStructure:
    def __init__(self):
        self.files = dict()
    
    def addFile(self, file):
        if self.files.get(file.getPath()) == None:
            self.files[file.getPath()] = [ file ]
        else:
            self.files[file.getPath()].append(file)

    def printFiles(self):
        retString = ""
        for key in self.files.keys():
            tabChr = '\t'
            retString += f'\n{tabChr * self.files[key][0].tab}{key}'
            for f in self.files[key]:
                retString += f.printFile()

    def writeFiles(self, fileName = "output.json"):
        allFiles = []
        allFiles.append({"type": "file"})
        for key in self.files.keys():
            for f in self.files[key]:
                allFiles.append(f.getFile())

        f = open(fileName, "w")
        f.write(json.dumps(allFiles, indent=4, sort_keys=True))
        f.close()

class folderStructure:
    def __init__(self):
        self.folders = dict()
    
    def addFile(self, file):
        if self.folders.get(file.getPath()) == None:
            self.folders[file.getPath()] = {
                "path": file.getPath(),
                "absPath": file.getAbsFileName(),
                "comparablePath": file.getCompPath(),
                "size": file.size,
                "files": 1,
                "tab": file.tab,
            }
        else:
            self.folders[file.getPath()]["size"] += file.size
            self.folders[file.getPath()]["files"] += 1

    def printFolders(self):
        for key in self.folders.keys():
            tabChr = '\t'
            return f'{tabChr * self.folders[key]["tab"]}{key}\t{self.folders[key]["path"]} ({self.folders[key]["files"]} - {getSize(self.folders[key]["size"], globalSizeConversion)})'

    def writeFolders(self, fileName = "output.json"):
        allFiles = []
        allFiles.append({"type": "folder"})
        for key in self.folders.keys():
            allFiles.append({
                "path": self.folders[key]["path"],
                "absPath": self.folders[key]["absPath"],
                "comparablePath": self.folders[key]["comparablePath"],
                "size": getSize(self.folders[key]["size"], globalSizeConversion),
                "files": self.folders[key]["files"],
            })

        f = open(fileName, "w")
        f.write(json.dumps(allFiles, indent=4, sort_keys=True))
        f.close()

class file:
    def __init__(self, path, fileName, root, tab):
        self.path = path
        self.fileName = fileName
        self.size = os.path.getsize(os.path.join(path, fileName))
        self.tab = tab
        self.root = root
    
    def getFileName(self):
        return self.fileName

    def getFullFileName(self):
        return os.path.join(self.path, self.fileName)

    def getAbsFileName(self):
        return os.path.abspath(os.path.join(self.path, self.fileName))

    def getPath(self):
        return self.path

    def getCompPath(self):
        # split root path which search started from, to current directory and remove it from path to get distinct values
        # remove first character from result as it is just the / character
        # append it with fileName
        # the final result gives a path that is more easily comparable with other directories
        return os.path.join(self.getPath().split(self.root,1)[1][1:], self.getFileName())

    def getFile(self):
        return {
            "path": self.getPath(),
            "absPath": self.getAbsFileName(),
            "comparablePath": self.getCompPath(),
            "fileName": self.getFileName(),
            "size": getSize(self.size, globalSizeConversion)
        }

    def printFile(self):
        tabChr = '\t'
        return f'{tabChr * self.tab}{self.fileName} ({getSize(self.size, globalSizeConversion)})'


#============================= DRIVER START =============================

def printHelper(shouldPrint, msg):
    if shouldPrint:
        print(msg)

def searchDirectory(currentDir, root, fileStruct, folderStruct, tab):
    for fname in os.listdir(currentDir):

        printHelper(tdebugger, f'Reached File: {os.path.join(currentDir, fname)}')

        nextFile = os.path.join(currentDir, fname)

        if os.path.isdir(nextFile):
            searchDirectory(nextFile, root, fileStruct, folderStruct, tab + 1)
        elif os.path.isfile(nextFile):
            fileObj = file(currentDir, fname, root, tab)
            fileStruct.addFile(fileObj)
            folderStruct.addFile(fileObj)


# parse all arguments into pre-defined variables
tdirectory, toutput, tquieter, tdebugger, tfolderAnalyze, tsize = parseAllArgs(args)

globalSizeConversion = tsize

fileStruct = fileStructure()
folderStruct = folderStructure()

printHelper(tdebugger, 'Starting Program..')

# Main Logic for analyzing directory
searchDirectory(tdirectory, tdirectory, fileStruct, folderStruct, 0)

printHelper(tdebugger, 'Program Finished')
printHelper(not tquieter, fileStruct.printFiles())

# Write out file structure
printHelper(tdebugger, f'Writing to {toutput}')
fileStruct.writeFiles(toutput)

# Only if argparsed folder param was found, then write out folder structure
if tfolderAnalyze:
    printHelper(not tquieter, folderStruct.printFolders())
    printHelper(tdebugger, f'Writing to folder.{toutput}')
    folderStruct.writeFolders(f'folder.{toutput}')

exit()