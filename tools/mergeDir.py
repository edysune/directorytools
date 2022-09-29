#mergeDir.py
# script that merges differences

import json 
import os
import argparse
import shutil
from paramiko import SSHClient

#============================= DEFINE DEFAULT AND GLOBAL VARIABLES =============================
# set and initialize variables used throughout the rest of the program
defaultDeleteConfirmNeeded = True
defaultMergeConfirmNeeded = True
defaultDebugger = True
defaultForce = False
defaultQuieter = True
validTypes = ["file"]
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
            print(f'Directory Does not exist remotely: {path}')
            return False
        raise
    else:
        return True

def removeFiles(tdebug, filesToRemove, removeAbsPath, confirmDeleteNeeded, tremote):
    printHelper(tdebug, f'Preparing to delete files: {removeAbsPath}...')
    skipAll = False
    skipNext = False
    if confirmDeleteNeeded:
        print("==== MENU ====\n(Y) To Confirm\n(N) Skip file\n(A) Abort\n(S) Skip All\n(C) Confirm All")

    deleteRemotely = tremote != None and tremote["mergeRemote"] != None and tremote["mergeRemote"]
    sftp = None
    ssh = None

    if deleteRemotely:
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
                print("Closing connections...")
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
                        print("Closing connections...")
                        sftp.close()
                        ssh.close()
                    exit()
                os.remove(file["absPath"])
                print(f'DELETED {file["absPath"]}')
            elif tremote["mergeRemote"]:
                sftp.remove(file["absPath"])
                print(f'DELETED {file["absPath"]}')

    if deleteRemotely:
        print("Closing connections...")
        sftp.close()
        ssh.close()
    printHelper(tdebug, f'Deleting files finished')

def mergeFiles(tdebug, filesToMerge, mergeAbsPath, deleteBasePath, confirmMergeNeeded, tremote):
    printHelper(tdebug, f'Preparing to merge files: {mergeAbsPath}...')
    skipAll = False
    skipNext = False
    if confirmMergeNeeded:
        print("==== MENU ====\n(Y) To Confirm\n(N) Skip file\n(A) Abort\n(S) Skip All\n(C) Confirm All")

    mergeToRemote = tremote != None and tremote["mergeRemote"] != None and tremote["mergeRemote"]
    sftp = None
    ssh = None

    if mergeToRemote:
        ssh = SSHClient() 
        ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
        ssh.connect(tremote["remote"], username=tremote["user"])
        sftp = ssh.open_sftp()


    for file in filesToMerge:
        if skipAll:
            print(f'SKIPPED: {file["absPath"]}:')
            continue

        if "fileName" not in file.keys() or "absPath" not in file.keys():
            printHelper(tdebug, f"MERGE ERROR: File name or Absolute Path is missing. Program exiting...")
            if mergeToRemote:
                print("Closing connections...")
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
                        print("Closing connections...")
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
                    print("Creating Directories...")
                    # todo: maybe catch exceptions around os.makedirs
                    os.makedirs(dstPath)

                shutil.copy2(src, dst)
                print(f'MERGED {dst}')
            elif tremote["mergeRemote"]:

                if not os.path.exists(file["absPath"]):
                    printHelper(tdebug, f"MERGE ERROR: directory {file['absPath']} does not exist - Please verify path")
                    if mergeToRemote:
                        print("Closing connections...")
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
                    print("CHECKING: " + curPath)
                    pathsToCreate.append(curPath)
                    curPath = os.path.dirname(curPath)
                    
                while len(pathsToCreate) > 0:
                    sftp.mkdir(pathsToCreate.pop())
 
                # todo - maybe do some error catching around this
                #for Uploading file from local to remote machine
                print("WRITING TO: " + dst)   
                sftp.put(src, dst)   
            else:
                print("MERGE ERROR - (copying from a remote directory [FALSE]) NOT IMPLEMENTED YET")
                # for Downloading a file from remote machine
                #sftp.get(‘remotefileth’,’localfilepath’)   
                if mergeToRemote:
                    print("Closing connections...")
                    sftp.close()
                    ssh.close()
                exit()


    printHelper(tdebug, f'Merging files finished')


# parse all arguments into pre-defined variables
tinput, tforce, tremote, tdebug = parseAllArgs(args)

printHelper(tdebug, 'Starting Program..')

deletes, merges, deleteBasePath, mergeBasePath = loadJsonFile(tinput)

printHelper(tdebug, f'Merge Abs Path: {mergeBasePath}\nNumber of files to merge: {len(merges)}')
printHelper(tdebug, f'Delete Abs Path: {deleteBasePath}\nNumber of files to delete: {len(deletes)}')

enforceFileType(merges)
enforceFileType(deletes)

removeFiles(tdebug, deletes, deleteBasePath, defaultDeleteConfirmNeeded, tremote)
mergeFiles(tdebug, merges, mergeBasePath, deleteBasePath, defaultMergeConfirmNeeded, tremote)

printHelper(tdebug, 'Program Finished')

exit()