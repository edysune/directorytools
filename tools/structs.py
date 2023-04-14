import json 
import os
import hashlib
import pathlib

#============================= Helper Functions =============================



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

#============================= STRUCTS =============================


class fileStructure:
    def __init__(self, os = 'win'):
        self.os = os
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
        rootPath = str(pathlib.PurePosixPath(rootDirectory)) if self.os == "linux" else os.path.abspath(rootDirectory)

        outerWrapper = {
            "os": self.os,
            "root": rootPath,
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
    def __init__(self, sizeConversion="KB"):
        self.sizeConversion = sizeConversion
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
            return f'{tabChr * self.folders[key]["tab"]}{key}\t{self.folders[key]["path"]} ({self.folders[key]["files"]} - {getSize(self.folders[key]["size"], self.sizeConversion)})'

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
                "size": getSize(self.folders[key]["size"], self.sizeConversion),
                "files": self.folders[key]["files"],
            })

        outerWrapper["files"] = allFiles

        f = open(fileName, "w")
        f.write(json.dumps(outerWrapper, indent=4, sort_keys=True))
        f.close()

class file:
    def __init__(self, path, fileName, root, tab, size=None, osType=None, sizeConversion="KB", sha256=None):
        self.path = path
        self.fileName = fileName
        if (size == None):
            self.size = os.path.getsize(os.path.join(path, fileName))
        else:
            self.size = size
        self.tab = tab
        self.root = root
        self.sizeConversion = sizeConversion
        self.sha256 = sha256
        self.os = osType
    
    def getFileName(self):
        return self.fileName

    def getFullFileName(self):
        return os.path.join(self.path, self.fileName)

    def getAbsFileName(self):
        tdir = os.path.join(self.path, self.fileName)
        if self.os == "linux":
            tdir = self.path + "/" + self.fileName
        return str(pathlib.PurePosixPath(tdir)) if self.os == "linux" else os.path.abspath(tdir)
 
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
        tdir = os.path.join(self.getAdjustedPath(), self.getFileName())
        if self.os == "linux":
            tdir = self.getAdjustedPath() + "/" + self.getFileName()
        return str(pathlib.PurePosixPath(tdir)) if self.os == "linux" else tdir

    def getCompPathPlain(self):
        return self.getCompPath().replace("\\", "/")

    def getFile(self):
        return {
            "path": self.getAdjustedPath(),
            "absPath": self.getAbsFileName(),
            "comparablePath": self.getCompPath(),
            "comparablePlainPath": self.getCompPathPlain(),
            "fileName": self.getFileName(),
            "size": getSize(self.size, self.sizeConversion)
        }

    def printFile(self):
        tabChr = '\t'
        return f'{tabChr * self.tab}{self.fileName} ({getSize(self.size, self.sizeConversion)})'

