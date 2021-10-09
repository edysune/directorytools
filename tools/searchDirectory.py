#searchDirectory.py

import json 
import os
import argparse


# 1.5) use argParse for better usability of tool, clean up imports


# 2) Compare 2 directories against each other - may need to look into GUI options? GUI options implies that we need a config file saved for this with reading/writing capabilities.

# 3) See about writing these types of things to a database

# 4) Create a GUI for this

# 5) Once in a database, should write some type of logic to merge into existing database

# 6) Should create logic around databases pulling information from database resource sites
# - Title Recommendations, Seasons, Episodes that do/don't exist, incomplete libraries, shows that are not found, bad structures of stuff

# 7) Possible additions to functionality like mass renaming of episodes and structures, update libraries logs, scan libraries for new data 

# 8) Possible subtitle downloading and merging? Not sure how useful this would be.


# Note: May need a way to group together similiar directories instead of just using absolute paths?
# Note: May need a tool for directory comparitors too - might be useful to have that as a top level tool before this

#============================= DEFINE VARIABLES =============================
#set and initialize variables used throughout the rest of the program
default_debugger = False
default_quieter = False
default_output_folder = 'output.json'

#directoryToSearch1 = "../test_dir/a1";
#directoryOutputFile1 = "../output/a1.json";
#directoryToSearch2 = "../test_dir/a2";
#directoryOutputFile2 = "../output/a2.json";

#============================= DEFINE ARGPARSE =============================
# construct the argument parser
ap = argparse.ArgumentParser()
ap.add_argument("-p", "--path", help="Path to the root directory to start analysis - Program will recursively analyze path for files and folders.")
ap.add_argument("-o", "--output", help="path and filename of output json file created. Defaults to output.json.")
ap.add_argument("-q", "--quiet", help="true/false or t/f supported. This argument quiets printing to the screen in a more readable tree-like structure aside from writing object to json.")
ap.add_argument("-d", "--debug", help="true/false or t/f supported. This argument turns debugging prints on/off, which gives slightly more information about program as it runs.")
args = vars(ap.parse_args())

#============================= DEFINE FUNCTIONS =============================
def parseAllArgs(args):
    #parse the arguments when program is used
    tdirectory = parseDirectory(args)
    toutput = parseOutputFile(args)
    tquieter = parseQuiet(args)
    tdebugger = parseDebug(args)
    return tdirectory, toutput, tquieter, tdebugger

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
#   toutput     a folder path. Program uses default json output file if not defined
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
        for key in self.files.keys():
            tabChr = '\t'
            print(f'\n{tabChr * self.files[key][0].tab}{key}')
            for f in self.files[key]:
                f.printFile(True)

    def writeFiles(self, fileName = "output.json"):
        allFiles = []
        for key in self.files.keys():
            for f in self.files[key]:
                allFiles.append(f.getFile())

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
    
    def getSize(self, conversion = "KB"):
        conversionRate = 1
        conversion = conversion.upper()

        if conversion == "B":
            return f'{self.size} {conversion}'

        #todo: refactor this, this is done horribly but shouldn't have much problems with simple data
        if conversion == "KB":
            conversionRate = 1000
        elif conversion == "MB":
            conversionRate = 1000000
        elif conversion == "GB":
            conversionRate = 1000000000

        return f'{self.size / conversionRate} {conversion}'

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
            "size": self.getSize()
        }

    def printFile(self, toConsole = False):
        tabChr = '\t'
        printedFile = f'{tabChr * self.tab}{self.fileName} ({self.getSize()})'
        if (toConsole):
            print(printedFile)
        return printedFile


#============================= DRIVER START =============================

def searchDirectory(currentDir, root, fStruct, tab):
    for fname in os.listdir(currentDir):
        #print(nextFile)
        nextFile = os.path.join(currentDir, fname)
        if os.path.isdir(nextFile):
            searchDirectory(nextFile, root, fStruct, tab + 1)
        elif os.path.isfile(nextFile):
            fStruct.addFile(file(currentDir, fname, root, tab))


#parse all arguments into pre-defined variables
tdirectory, toutput, tquieter, tdebugger = parseAllArgs(args)

directoryStruct = fileStructure()
searchDirectory(tdirectory, tdirectory, directoryStruct, 0)
if tquieter:
    directoryStruct.printFiles()

directoryStruct.writeFiles(toutput)

exit()