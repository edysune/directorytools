#mergeDir.py
# script that merges differences

import json 
import os
import argparse
import shutil
import math
import sys
from paramiko import SSHClient

#============================= DEFINE DEFAULT AND GLOBAL VARIABLES =============================
# set and initialize variables used throughout the rest of the program
defaultDeleteConfirmNeeded = True
defaultMergeConfirmNeeded = True
defaultDebugger = False
defaultForce = False
defaultQuieter = True
validTypes = ["file"]
menuString = "(Y) To Confirm\t(N) Skip file\t(A) Abort\t(S) Skip All\t(C) Confirm All\n"

#============================= DEFINE ARGPARSE =============================
# construct the argument parser
ap = argparse.ArgumentParser()
ap.add_argument("-i", "--input", help="path and filename of the diff json object")
ap.add_argument("-mr", "--mergeOnRemote", help="true/false or t/f supported. This is true if you are trying to copy files over to a remote machine. false if the opposite is true")
ap.add_argument("-f", "--force", help="true/false or t/f supported. This argument forces merge to do a complete sync, including removing files. Do not use for partial merges.")
ap.add_argument("-d", "--debug", help="true/false or t/f supported. This argument turns debugging prints on/off, which gives slightly more information about program as it runs.")
ap.add_argument("-r", "--remote", help="Script uses SSH to connect via server url. It's assumed to be local unless this flag is active")
ap.add_argument("-u", "--user", help="user for remote SSH. Not needed for local usage.")
ap.add_argument("-p", "--port", help="port for remote SSH. Not needed for local usage.")
args = vars(ap.parse_args())

#============================= DEFINE FUNCTIONS =============================
def parseAllArgs(args):
    # parse the arguments when program is used
    tinput = parseInput(args)
    tforce = parseForce(args)
    tremote = parseRemote(args)
    tdebug = parseDebug(args)
    return tinput, tforce, tremote, tdebug

#Preconditions: None
#Postconditions: None
#Arguments:
#   args         a dictionary containing directory keys. 1 input containing valid file paths must be given.
#Returns:
#   tinput       1 input file with valid path. Program exits if it doesn't exist.
def parseInput(args) :
    if args["input"] is None:
        print("-i <DIFF INPUT PATH + FILENAME> is not defined\nPlease see HELP screen for more information about how to use this program.")
        exit()
    tinput = args["input"]
    if not os.path.exists(tinput):
        print(f"Error: directory {tinput} does not exist - Please verify path")
        exit()
    return tinput

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing output keys. Is not a required field.
#Returns:
#   tdebug     
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

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing output keys. Is not a required field.
#Returns:
#   tforce     
def parseForce(args):
    if args["force"] is None:
        return defaultForce

    tforce = args["force"].lower()
    if tforce == "true" or tforce == "t":
        return True
    elif tforce == "false" or tforce == "f":
        return False
    else:
        print(f"Error: force argument {tforce} not true/false or t/f - defaulting to {defaultForce}")
        return defaultForce

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        
#Returns:
#   tsize        
def parseRemote(args):
    if args["remote"] is None:
        return None

    # todo: do null checks on all arguments
    remote = args["remote"]
    user = args["user"]
    port = args["port"]

    mergeRemotely = args["mergeOnRemote"]

    if mergeRemotely is None:
        return {"remote": remote, "user": user, "port": port, "mergeRemote": False}

    if mergeRemotely == "true" or mergeRemotely == "t":
        mergeRemotely = True
    elif mergeRemotely == "false" or mergeRemotely == "f":
        mergeRemotely = False

    return {"remote": remote, "user": user, "port": port, "mergeRemote": mergeRemotely}


#============================= DRIVER START =============================

def progressbar(x, y, prePrint = "", postPrint = ""):
    bar_len = 60
    filled_len = math.ceil(bar_len * x / float(y))
    percents = math.ceil(100.0 * x / float(y))
    bar = '=' * filled_len + '-' * (bar_len - filled_len)
    filesize = f'{math.ceil(y/1024):,} KB' if y > 1024 else f'{y} byte'
    sys.stdout.write(f'{prePrint}[{bar}] {percents}% {filesize}{postPrint}\r')
    sys.stdout.flush()

def printHelper(shouldPrint, msg):
    if shouldPrint:
        print(msg)

def loadJsonFile(file):
    f = open(file,)
    data = json.load(f)

    instructions = data['metadata']

    if instructions == None:
        print("Error - no metadata")
        exit()

    mergeKey = instructions["mergeScan"]
    mergeBasePath = instructions["mergeRootPath"]
    deleteKey = instructions["deleteScan"]
    deleteBasePath = instructions["deleteRootPath"]

    if mergeKey == None or deleteKey == None or mergeBasePath == None or deleteBasePath == None :
        print("Error - no scan instructions or base path")
        exit()

    merges = data[mergeKey]
    deletes = data[deleteKey]

    if merges == None or deletes == None :
        print("Error - no object found")
        exit()

    return deletes, merges, deleteBasePath, mergeBasePath

def enforceFileType(files):
    for item in files:
        if item["type"] == None or item["type"] == "folder":
            print(f"File type is not valid. Program exiting...")
            exit()

def handleInput(actionType, path):
    
    while True:
        userInput = input(f"{actionType}: {path} | ")
        userInput = userInput.upper()

        if userInput == "Y":
            return True, False, False
        elif userInput == "N":
            print(f'SKIPPED.')
            return True, False, True
        elif userInput == "S":
            print(f'SKIPPED')
            return True, True, True   
        elif userInput == "C":
            return False, False, False
        elif userInput == "A":
            print("\nABORTING...")
            exit()
        else:
            print("\nINVALID INPUT\n")

def remoteExists(sftp, path):
    """os.path.exists for paramiko's SCP object
    """
    try:
        sftp.stat(path)
    except IOError as e:
        if 'No such file' in str(e):
            # print(f'Directory Does not exist remotely: {path}')
            return False
        raise
    else:
        return True

def removeFiles(tdebug, filesToRemove, removeAbsPath, confirmDeleteNeeded, tremote):
    skipAll = False
    skipNext = False

    printHelper(confirmDeleteNeeded and len(filesToRemove) > 0, menuString)

    deleteRemotely = tremote != None and tremote["mergeRemote"] != None and tremote["mergeRemote"]
    sftp = None
    ssh = None

    if deleteRemotely and len(filesToRemove) > 0:
        ssh = SSHClient() 
        ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
        ssh.connect(tremote["remote"], username=tremote["user"])
        sftp = ssh.open_sftp()

    for file in filesToRemove:
        if skipAll:
            print(f'SKIPPED: {file["absPath"]}:')
            continue

        if "fileName" not in file.keys() or "absPath" not in file.keys():
            printHelper(tdebug, f"DELETE ERROR: File name or Absolute Path is missing. Program exiting...")
            if deleteRemotely:
                printHelper(tdebug, "Closing connections...")
                sftp.close()
                ssh.close()
            exit()

        if confirmDeleteNeeded:
            confirmDeleteNeeded, skipAll, skipNext = handleInput("DELETE?", file['absPath'])

        if not skipNext:
            if tremote == None or tremote["mergeRemote"] == None or not tremote["mergeRemote"]:
                # todo: maybe catch exceptions around os.remove
                if not os.path.exists(file["absPath"]):
                    printHelper(tdebug, f"DELETE ERROR: directory {file['absPath']} does not exist - Please verify path")
                    if deleteRemotely:
                        printHelper(tdebug, "Closing connections...")
                        sftp.close()
                        ssh.close()
                    exit()
                os.remove(file["absPath"])
                printHelper(not confirmDeleteNeeded, f'DELETED {file["absPath"]}')
            elif tremote["mergeRemote"]:
                sftp.remove(file["absPath"])
                printHelper(not confirmDeleteNeeded, f'DELETED {file["absPath"]}')

    if deleteRemotely and len(filesToRemove) > 0:
        printHelper(tdebug, "Closing connections...")
        sftp.close()
        ssh.close()
    printHelper(tdebug, f'Deleting files finished')

def mergeFiles(tdebug, filesToMerge, mergeAbsPath, deleteBasePath, confirmMergeNeeded, tremote):
    skipAll = False
    skipNext = False

    printHelper(confirmMergeNeeded and len(filesToMerge) > 0, menuString)

    mergeToRemote = tremote != None and tremote["mergeRemote"] != None and tremote["mergeRemote"]
    sftp = None
    ssh = None

    if mergeToRemote and len(filesToMerge) > 0:
        ssh = SSHClient() 
        ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
        ssh.connect(tremote["remote"], username=tremote["user"])
        sftp = ssh.open_sftp()

    totalFiles = len(filesToMerge)
    currentFileNum = 0

    for file in filesToMerge:
        currentFileNum += 1
        if skipAll:
            print(f'SKIPPED: {file["absPath"]}:')
            continue

        if "fileName" not in file.keys() or "absPath" not in file.keys():
            printHelper(tdebug, f"MERGE ERROR: File name or Absolute Path is missing. Program exiting...")
            if mergeToRemote:
                printHelper(tdebug, "Closing connections...")
                sftp.close()
                ssh.close()
            exit()

        if confirmMergeNeeded:
            confirmMergeNeeded, skipAll, skipNext = handleInput("MERGE?", file['absPath'])

        if not skipNext:
            if tremote == None or tremote["mergeRemote"] == None:
                if not os.path.exists(file["absPath"]):
                    printHelper(tdebug, f"MERGE ERROR: directory {file['absPath']} does not exist - Please verify path")
                    if mergeToRemote:
                        printHelper(tdebug, "Closing connections...")
                        sftp.close()
                        ssh.close()
                    exit()

                # todo: maybe catch exceptions around os.copy2
                src = file["absPath"]

                pathToFile = file["comparablePath"]

                dst = os.path.join(deleteBasePath, pathToFile)
                dstPath = os.path.dirname(dst)

                dstPathExists = os.path.exists(dstPath)

                if not dstPathExists:
                    # print("Creating Directories...")
                    # todo: maybe catch exceptions around os.makedirs
                    os.makedirs(dstPath)

                shutil.copy2(src, dst)
                print()
                printHelper(not confirmMergeNeeded, f'MERGED {dst}')
            elif tremote["mergeRemote"]:

                if not os.path.exists(file["absPath"]):
                    printHelper(tdebug, f"MERGE ERROR: directory {file['absPath']} does not exist - Please verify path")
                    if mergeToRemote:
                        printHelper(tdebug, "Closing connections...")
                        sftp.close()
                        ssh.close()
                    exit()

                src = file["absPath"]
                pathToFile = file["comparablePath"]
                dst = os.path.join(deleteBasePath, pathToFile)
                dstPath = os.path.dirname(dst)
                
                curPath = dstPath
                pathsToCreate = []

                while not remoteExists(sftp, curPath):
                    # print("CHECKING: " + curPath)
                    pathsToCreate.append(curPath)
                    curPath = os.path.dirname(curPath)
                    
                while len(pathsToCreate) > 0:
                    sftp.mkdir(pathsToCreate.pop())
 
                # todo - maybe do some error catching around this
                #for Uploading file from local to remote machine
                printHelper(not confirmMergeNeeded, f'MERGED {dst}')

                sftp.put(src, dst, callback=lambda x,y: progressbar(x,y, f"({currentFileNum}/{totalFiles}) "))
                sys.stdout.flush()
            else:
                print("MERGE ERROR - (copying from a remote directory [FALSE]) NOT IMPLEMENTED YET")
                # for Downloading a file from remote machine
                #sftp.get(‘remotefileth’,’localfilepath’)   
                if mergeToRemote:
                    printHelper(tdebug, "Closing connections...")
                    sftp.close()
                    ssh.close()
                exit()


    printHelper(tdebug, f'Merging files finished')


# parse all arguments into pre-defined variables
tinput, tforce, tremote, tdebug = parseAllArgs(args)

printHelper(tdebug, 'Starting Program..')

deletes, merges, deleteBasePath, mergeBasePath = loadJsonFile(tinput)

print(f'\nDelete\t({len(deletes)}):\t{deleteBasePath}')
print(f'Merge\t({len(merges)}):\t{mergeBasePath}\n')

enforceFileType(merges)
enforceFileType(deletes)

removeFiles(tdebug, deletes, deleteBasePath, defaultDeleteConfirmNeeded, tremote)
mergeFiles(tdebug, merges, mergeBasePath, deleteBasePath, defaultMergeConfirmNeeded, tremote)

printHelper(tdebug, 'Program Finished')

exit()