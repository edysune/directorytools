#compareDir.py
# script that compares 2 directories against each other

import json 
import os
import argparse

#============================= DEFINE DEFAULT AND GLOBAL VARIABLES =============================
# set and initialize variables used throughout the rest of the program
printLoadedFiles = False
debugMatches = False
defaultDebugger = False
defaultQuieter = True
useLegacyComparator = False
defaultOutputFolder = 'output.comp.json'
validTypes = ["folder", "file"]

#============================= DEFINE ARGPARSE =============================
# construct the argument parser
ap = argparse.ArgumentParser()
ap.add_argument("-i", "--input", help="file name and paths to 2 input files to compare with each other. Files must match in terms of content type (folders, files, etc).", nargs=2)
ap.add_argument("-o", "--output", help=f"path and filename of output json file created. Defaults to {defaultOutputFolder}.")
ap.add_argument("-d", "--debug", help="true/false or t/f supported. This argument turns debugging prints on/off, which gives slightly more information about program as it runs.")
args = vars(ap.parse_args())

#============================= DEFINE FUNCTIONS =============================
def parseAllArgs(args):
    # parse the arguments when program is used
    tinput = parseInput(args)
    toutput = parseOutputFile(args)
    tdebug = parseDebug(args)
    return tinput, toutput, tdebug

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing directory keys. At least 2 inputs containing valid file paths must be given.
#Returns:
#   paths     2 input file with valid parths. Program exits if it doesn't exist, or if 2 are not specifically given.
def parseInput(args) :
    if args["input"] is None or not isinstance(args["input"], list) or len(args["input"]) != 2:
        print("-i <INPUT 1> <INPUT 2> is not given correctly\nPlease see HELP screen for more information about how to use this program.")
        exit()
    paths = args["input"]
    for path in paths:
        if not os.path.exists(path):
            print(f"Error: directory {path} does not exist - Please verify path")
            exit()
    return paths

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing output keys. Is not a required field.
#Returns:
#   toutput     an output file name. Program uses default json output file if not defined
def parseOutputFile(args):
    if args["output"] is None:
        return defaultOutputFolder
    return args["output"]

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing output keys. Is not a required field.
#Returns:
#   tdebug     a folder path. Program uses default json output file if not defined
def parseDebug(args):
    if args["debug"] is None:
        return defaultDebugger

    tdebug = args["debug"].lower()
    if tdebug == "true" or tdebug == "t":
        return True
    elif tdebug == "false" or tdebug == "f":
        return False
    else:
        print(f"Error: debug argument {tdebug} not true/false or t/f - defaulting to {defaultDebugger}")
        return defaultDebugger


#============================= SUPPLEMENTAL CLASSES =============================

class FileComparableObj:
    def __init__(self, jsonData, fileType):
        self.fileType = fileType

        if self.fileType == "file":
            self.comparablePath = jsonData['comparablePath'] if "comparablePath" in jsonData else "N/A"
            self.comparablePlainPath = jsonData['comparablePlainPath'] if "comparablePlainPath" in jsonData else "N/A"
            self.path = jsonData['path'] if "path" in jsonData else "N/A"
            self.absPath = jsonData['absPath'] if "absPath" in jsonData else "N/A"
            self.size = jsonData['size'] if "size" in jsonData else "N/A"
            self.fileName = jsonData['fileName'] if "fileName" in jsonData else "N/A"
        elif self.fileType == "folder":
            self.path = jsonData['path'] if "path" in jsonData else "N/A"
            self.absPath = jsonData['absPath'] if "absPath" in jsonData else "N/A"
            self.size = jsonData['size'] if "size" in jsonData else "N/A"
            self.files = jsonData["files"] if "files" in jsonData else -1

    def hasFiles(self):
        return False if self.files == -1 else True

    def getFiles(self):
        return self.files

    def getSize(self):
        return self.size

    def getAbsPath(self):
        return self.absPath

    def getPath(self):
        return self.path

    def getComparablePath(self):
        return self.comparablePath

    def getFileName(self):
        return self.fileName

    def getFileType(self):
        return self.fileType

    def getCompPathPlain(self):
        return self.comparablePlainPath

    def getJSON(self):
        if self.getFileType() == "file":     
            return {
                "fileName": self.getFileName(),
                "size": self.getSize(),
                "absPath": self.getAbsPath(),
                "path": self.getPath(),
                "comparablePath": self.getComparablePath(),
                "comparablePlainPath": self.getCompPathPlain(),
                "type": self.getFileType(),
            }
        if self.getFileType() == "folder":     
            return {
                "files": self.getFiles(),
                "size": self.getSize(),
                "absPath": self.getAbsPath(),
                "path": self.getPath(),
                "type": self.getFileType(),
            }
        return {
            "error" : self.getFileType() + " is an invalid file type"
        }

    def isFileIn(file, files, isFolder):
        return any(FileComparableObj.isSameFile(nextFile, file, isFolder) for nextFile in files)

    def isSameFile(file1, file2, isFolder):
        if isFolder:
            if file1.getSize() != file2.getSize():
                return False
            if file1.getFiles() != file2.getFiles():
                return False
            return True
        else:
            if file1.getCompPathPlain() != file2.getCompPathPlain():
                return False
            if file1.getSize() != file2.getSize():
                return False
            return True

    def print(self):
        files = '' if self.getFiles() == -1 else f"{self.getFiles()}"
        print(f"{self.getComparablePath()}\t{files}\t{self.getSize()}")
        

#============================= DRIVER START =============================

def printHelper(shouldPrint, msg):
    if shouldPrint:
        print(msg)

def loadJsonFile(file):
    f = open(file,)
    data = json.load(f)

    # resDict => for faster lookups when comparing
    resDict = dict()

    res = []
    fileType = data['type'].lower()
    fileRoot = data['root']
    fileOs = data['os']

    if fileType != "file" and fileType != "folder":
        print(f"ERROR - file type {fileType} is neither file nor folder. Exiting program..")
        exit()

    for file in data['files']:
        f = FileComparableObj(file, fileType)
        resDict[f.getCompPathPlain()] = f
        res.append(f)
    return fileType, res, resDict, fileRoot, fileOs

def enforceFileType(ftype1, ftype2, tinput):
    if ftype1 != ftype2:
        print(f"File type {ftype1} from {tinput[0]} does not match {ftype2} from {tinput[1]} . Program exiting...")
        exit()
    if ftype1 not in validTypes:
        print(f"File type {ftype1} from {tinput[0]} is not valid. Program exiting...")
        exit()
    if ftype2 not in validTypes:
        print(f"File type {ftype2} from {tinput[1]} is not valid. Program exiting...")
        exit()

def findDifferences(tdebug, filesA, filesB, isFolder, filesDictA, filesDictB):
    diffs = []

    if useLegacyComparator:
        printHelper(tdebug, 'Using Legacy Comparator.')
        # has n * m complexity with usage of lists
        for a in filesA:
            if not FileComparableObj.isFileIn(a, filesB, isFolder):
                diffs.append(a)
    else:
        printHelper(tdebug, 'Using Quick Comparator.')
        # has n complexity with usage of dictionarys
        for fileComparablePath in filesDictA.keys():
            fileB = filesDictB.get(fileComparablePath)
            if fileB == None:
                # if file never existed on second dictionary
                printHelper(tdebug, 'New File: ' + fileComparablePath)
                diffs.append(filesDictA[fileComparablePath])
            elif not FileComparableObj.isSameFile(filesDictA[fileComparablePath], fileB, isFolder):
                # If file did exist but is different (updated/edited)
                printHelper(tdebug, 'Updated File: ' + fileComparablePath)
                diffs.append(filesDictA[fileComparablePath])

    return diffs

def printResults(tdebug, tinput, diffAToB, diffBToA):
    if tdebug:
        if(len(diffAToB) > 0):
            print(f"Files in {tinput[0]} => {tinput[1]} have {len(diffAToB)} differences")
        else:
            print(f"Files in {tinput[0]} => {tinput[1]} are matched perfectly.")
        if(len(diffBToA) > 0):
            print(f"Files in {tinput[1]} => {tinput[0]} have {len(diffBToA)} differences")
        else:
            print(f"Files in {tinput[1]} => {tinput[0]} are matched perfectly.")

def printLoad(fileName, ftype, files):
    if tdebug:
        print(f"{fileName} loaded {len(files)} items as {ftype}.")  
        if printLoadedFiles:
            for e in files:
                e.print()      

def generateFileDiff(diffList):
    convertedFiles = []
    for file in diffList:
        # todo: go through each and add another field in JSON that explains why there is a difference
        convertedFiles.append(file.getJSON())

    return convertedFiles

def writeFileDiff(diffRootA, diffListA, diffRootDirA, fileTypeA, fileOsA, diffRootB, diffListB, diffRootDirB, fileTypeB, fileOsB, fileName):
    fout = {}
    fout["metadata"] = { "warning": "unsupported features with folders will not allow syncing"} if fileTypeA != fileTypeB or fileTypeA == "folder" else {
        "mergeScan": diffRootA,
        "mergeRootPath": diffRootDirA,
        "mergeFilesNum": len(diffListA),
        "mergeFilesOs": fileOsA,
        "deleteScan": diffRootB,
        "deleteRootPath": diffRootDirB,
        "deleteFilesNum": len(diffListB),
        "deleteFilesOs": fileOsB,
    }

    # todo: diffRoot's are the jsonfile, not the actual path. Will probably need this.
    fout[diffRootA] = generateFileDiff(diffListA)
    fout[diffRootB] = generateFileDiff(diffListB)

    f = open(fileName, "w")
    f.write(json.dumps(fout, indent=4, sort_keys=True))
    f.close()

# parse all arguments into pre-defined variables
tinput, toutput, tdebug = parseAllArgs(args)

printHelper(tdebug, 'Starting Program..')

ftype1, files1, filesDict1, rootDir1, fileOs1 = loadJsonFile(tinput[0])
ftype2, files2, filesDict2, rootDir2, fileOs2 = loadJsonFile(tinput[1])

printLoad(tinput[0], ftype1, files1)
printLoad(tinput[1], ftype2, files2)

#check matching types
enforceFileType(ftype1, ftype2, tinput)

#Compare a to b
#Compare b to a
diffAToB = findDifferences(tdebug, files1, files2, ftype1 == "folder", filesDict1, filesDict2)
diffBToA = findDifferences(tdebug, files2, files1, ftype2 == "folder", filesDict2, filesDict1)

writeFileDiff(
    tinput[0], diffAToB, rootDir1, ftype1, fileOs1,
    tinput[1], diffBToA, rootDir2, ftype2, fileOs2,
    toutput
)

printResults(tdebug, tinput, diffAToB, diffBToA)

printHelper(tdebug, 'Program Finished')

exit()