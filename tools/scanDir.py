#scanDir.py

import json 
import os
import argparse
from paramiko import SSHClient
from stat import S_ISDIR, S_ISREG

#============================= DEFINE DEFAULT AND GLOBAL VARIABLES =============================
# set and initialize variables used throughout the rest of the program
default_debugger = False
default_quieter = True
default_folderAnalyze = True
default_output_folder = 'output.json'
default_size = "KB"

globalSizeConversion = ""

#============================= DEFINE ARGPARSE =============================
# construct the argument parser
ap = argparse.ArgumentParser()
ap.add_argument("-d", "--directory", help="Path to the root directory to start analysis - Program will recursively analyze path for files and folders.")
ap.add_argument("-f", "--folder", help="true/false or t/f supported. This argument analyzes folder structs as a whole, instead of individual files. This will run alongside the file program, and output to folder.<output.json>.")
ap.add_argument("-s", "--size", help="Conversion Size for file output. B, KB, MB, GB are supported currently. KB is set by default unless specified otherwise.")
ap.add_argument("-o", "--output", help="path and filename of output json file created. Defaults to output.json.")
ap.add_argument("-q", "--quiet", help="true/false or t/f supported. This argument quiets printing to the screen in a more readable tree-like structure aside from writing object to json.")
# ap.add_argument("-d", "--debug", help="true/false or t/f supported. This argument turns debugging prints on/off, which gives slightly more information about program as it runs.")
ap.add_argument("-r", "--remote", help="Script uses SSH to connect via server url. It's assumed to be local unless this flag is active")
ap.add_argument("-u", "--user", help="user for remote SSH. Not needed for local usage.")
ap.add_argument("-p", "--port", help="port for remote SSH. Not needed for local usage.")
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
    tremote = parseRemote(args)
    return tdirectory, toutput, tquieter, tdebugger, tfolderAnalyze, tsize, tremote

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing directory keys. At least 1 must be something other than None
#Returns:
#   tdirectory     a folder path. Program exits if it doesn't exist.
def parseDirectory(args):
    if args["directory"] is None:
        print("-d <SCAN PATH DIRECTORY> is not defined\nPlease see HELP screen for more information about how to use this program.")
        exit()
    tdirectory = args["directory"]
    # if not os.path.exists(tdirectory):
    #     print(f"Error: directory {tdirectory} does not exist - Please verify path")
    #     exit()
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

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        
#Returns:
#   tsize        
def parseRemote(args):
    if args["remote"] is None:
        return None

    remote = args["remote"]
    user = args["user"]
    port = args["port"]

    return {"remote": remote, "user": user, "port": port}



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

    def writeFiles(self, rootDirectory, fileName = "output.json"):
        outerWrapper = {
            "root": os.path.abspath(rootDirectory),
            "type": "file"
            }
        allFiles = []
        for key in self.files.keys():
            for f in self.files[key]:
                allFiles.append(f.getFile())

        outerWrapper["files"] = allFiles

        f = open(fileName, "w")
        f.write(json.dumps(outerWrapper, indent=4, sort_keys=True))
        f.close()

class folderStructure:
    def __init__(self):
        self.folders = dict()
    
    def addFile(self, file):
        if self.folders.get(file.getPath()) == None:
            self.folders[file.getPath()] = {
                "path": file.getAdjustedPath(),
                "absPath": file.getAbsPath(),
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

    def writeFolders(self, rootDirectory, fileName = "output.json"):
        outerWrapper = {
            "root": os.path.abspath(rootDirectory),
            "type": "folder"
        }

        allFiles = []
        for key in self.folders.keys():
            allFiles.append({
                "path": self.folders[key]["path"],
                "absPath": self.folders[key]["absPath"],
                "size": getSize(self.folders[key]["size"], globalSizeConversion),
                "files": self.folders[key]["files"],
            })

        outerWrapper["files"] = allFiles

        f = open(fileName, "w")
        f.write(json.dumps(outerWrapper, indent=4, sort_keys=True))
        f.close()

class file:
    def __init__(self, path, fileName, root, tab, size=None):
        self.path = path
        self.fileName = fileName
        if (size == None):
            self.size = os.path.getsize(os.path.join(path, fileName))
        else:
            self.size = size;
        self.tab = tab
        self.root = root
    
    def getFileName(self):
        return self.fileName

    def getFullFileName(self):
        return os.path.join(self.path, self.fileName)

    def getAbsFileName(self):
        return os.path.abspath(os.path.join(self.path, self.fileName))
 
    def getAbsPath(self):
        # todo: need to return absolute path without the trailing file
        #return self.getAbsFileName().split(os.path.abspath(self.path))[0]
        return self.getAbsFileName()

    def getPath(self):
        return self.path

    def getAdjustedPath(self):
        path = self.getPath().split(self.root,1)[1]
        while path != "" and path[0] == "\\" or  path[0] == "/":
            path = path[1:]
        return path

    def getCompPath(self):
        # split root path which search started from, to current directory and remove it from path to get distinct values
        # remove first character from result as it is just the / character
        # append it with fileName
        # the final result gives a path that is more easily comparable with other directories
        return os.path.join(self.getAdjustedPath(), self.getFileName())

    def getFile(self):
        return {
            "path": self.getAdjustedPath(),
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

def scanDirectory(currentDir, root, fileStruct, folderStruct, tab):
    if not os.path.exists(currentDir):
        print(f"Error: directory {currentDir} does not exist - Please verify path")
        exit()

    for fname in os.listdir(currentDir):

        printHelper(tdebugger, f'Reached File: {os.path.join(currentDir, fname)}')

        nextFile = os.path.join(currentDir, fname)

        if os.path.isdir(nextFile):
            scanDirectory(nextFile, root, fileStruct, folderStruct, tab + 1)
        elif os.path.isfile(nextFile):
            fileObj = file(currentDir, fname, root, tab)
            fileStruct.addFile(fileObj)
            folderStruct.addFile(fileObj)

def scanDirectoryRemotely(remoteInput, currentDir, root, fileStruct, tab):
    printHelper(tdebugger, "Attempting to connect via SSH...")

    ssh = SSHClient() 
    ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
    ssh.connect(remoteInput["remote"], username=remoteInput["user"])
    sftp = ssh.open_sftp()

    printHelper(tdebugger, f"Connecting to {currentDir}")

    # print(sftp.listdir(currentDir))
    scanRemotely(sftp, currentDir, root, fileStruct, tab)

    printHelper(tdebugger, "Closing connections...")
    sftp.close()
    ssh.close()

def scanRemotely(sftp, currentDir, root, fileStruct, tab):
    for entry in sftp.listdir_attr(currentDir):
        # https://stackoverflow.com/questions/70928978/sftp-how-to-list-large-of-files
        # May want to start here next, as I'm not making much progress, and removing a ton of my files just doesn't seem useful
        nextFile = os.path.join(currentDir, entry.filename)
        printHelper(tdebugger, f'Reached File: {nextFile}')

        mode = entry.st_mode
        if S_ISDIR(mode):
            # todo: may need to see if there is a safer way to join these 2, as \\ may not be safe to use for all os's
            scanRemotely(sftp, currentDir + "\\" + entry.filename, root, fileStruct, tab + 1)
        elif S_ISREG(mode):
            fileObj = file(currentDir, entry.filename, root, tab, entry.st_size)
            fileStruct.addFile(fileObj)


# parse all arguments into pre-defined variables
tdirectory, toutput, tquieter, tdebugger, tfolderAnalyze, tsize, tremote = parseAllArgs(args)

globalSizeConversion = tsize

fileStruct = fileStructure()
folderStruct = folderStructure()

printHelper(tdebugger, 'Starting Program..')

if tremote != None:
    scanDirectoryRemotely(tremote, tdirectory, tdirectory, fileStruct, 0)
else:
    # Main Logic for analyzing directory
    scanDirectory(tdirectory, tdirectory, fileStruct, folderStruct, 0)

printHelper(tdebugger, 'Program Finished')
printHelper(not tquieter, fileStruct.printFiles())

# Write out file structure
printHelper(tdebugger, f'Writing to {toutput}')
fileStruct.writeFiles(tdirectory, toutput)

# Only if argparsed folder param was found, then write out folder structure
if tfolderAnalyze:
    printHelper(not tquieter, folderStruct.printFolders())
    printHelper(tdebugger, f'Writing to folder.{toutput}')
    folderStruct.writeFolders(tdirectory, f'folder.{toutput}')

exit()