#cleanUpDir.py

import json 
import os
import argparse
from paramiko import SSHClient
from stat import S_ISDIR, S_ISREG
from structs import *
from commonParserLib import *

#============================= DEFINE DEFAULT AND GLOBAL VARIABLES =============================
# set and initialize variables used throughout the rest of the program
default_debugger = False
default_quieter = True
default_os = "win"
default_auto_delete_empty_folders = True
menuString = "(Y) To Delete\t(N) Skip file\t(A) Abort\t(S) Skip All\t(D) Delete All\n"

#============================= DEFINE ARGPARSE =============================
# construct the argument parser
ap = argparse.ArgumentParser()
ap.add_argument("-d", "--directory", help="Path to the root directory to start analysis - Program will recursively analyze path for files and folders.")
# ap.add_argument("-q", "--quiet", help="true/false or t/f supported. This argument quiets printing to the screen in a more readable tree-like structure aside from writing object to json.")
# ap.add_argument("-d", "--debug", help="true/false or t/f supported. This argument turns debugging prints on/off, which gives slightly more information about program as it runs.")
ap.add_argument("-r", "--remote", help="Script uses SSH to connect via server url. It's assumed to be local unless this flag is active")
ap.add_argument("-u", "--user", help="user for remote SSH. Not needed for local usage.")
ap.add_argument("-p", "--port", help="port for remote SSH. Not needed for local usage.")
ap.add_argument("-c", "--cred", help="password for remote SSH. Not needed for local usage.")
ap.add_argument("-os", "--osys", help="operating system. Defaults to 'win'.")
args = vars(ap.parse_args())

#============================= DEFINE FUNCTIONS =============================
def parseAllArgs(args):
    # parse the arguments when program is used
    tdirectory = parseDirectory(args)
    tquieter = parseQuiet(args, default_quieter)
    tdebugger = parseDebug(args, default_debugger)
    tremote = parseRemote(args)
    tos = parseOs(args, default_os)
    return tdirectory, tquieter, tdebugger, tremote, tos

#============================= DRIVER START =============================

def printHelper(shouldPrint, msg):
    if shouldPrint:
        print(msg)

def scanDirectory(currentDir, root, fileStruct, folderStruct, tab):
    raise Exception("NOT IMPLEMENTED - scanDirectory")
    # if not os.path.exists(currentDir):
    #     print(f"Error: directory {currentDir} does not exist - Please verify path")
    #     exit()

    # for fname in os.listdir(currentDir):

    #     printHelper(tdebugger, f'Reached File: {os.path.join(currentDir, fname)}')

    #     nextFile = os.path.join(currentDir, fname)

    #     if os.path.isdir(nextFile):
    #         scanDirectory(nextFile, root, fileStruct, folderStruct, tab + 1)
    #     elif os.path.isfile(nextFile):

    #         fileSha256 = calcSha256Locally(nextFile)
    #         fileObj = file(currentDir, fname, root, tab)
    #         fileStruct.addFile(fileObj)
    #         folderStruct.addFile(fileObj)

class InputConfig:
  def __init__(self, confirmDeleteNeeded = not default_auto_delete_empty_folders, skipAll = False, skipNext = False):
    self.confirmDeleteNeeded = confirmDeleteNeeded
    self.skipAll = skipAll
    self.skipNext = skipNext

def scanDirectoryRemotely(remoteInput, currentDir, root, tab, tos):
    printHelper(tdebugger, "Attempting to connect via SSH...")

    ssh = SSHClient() 
    ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
    if remoteInput["password"] != None:
        ssh.connect(remoteInput["remote"], username=remoteInput["user"], password=remoteInput["password"])
    else:
        ssh.connect(remoteInput["remote"], username=remoteInput["user"])
    sftp = ssh.open_sftp()

    printHelper(tdebugger, f"Connecting to {currentDir}")

    # print(sftp.listdir(currentDir))
    inputConfig = InputConfig()
    scanRemotely(sftp, currentDir, root, tab, tos, inputConfig)

    printHelper(tdebugger, "Closing connections...")
    sftp.close()
    ssh.close()

def scanRemotely(sftp, currentDir, root, tab, tos, inputConfig):
    isRoot = currentDir == root

    if not isRoot and len(sftp.listdir_attr(currentDir)) == 0:
        removedFile, inputConfig = removeFileRemotely(currentDir, sftp, inputConfig)
        return

    for entry in sftp.listdir_attr(currentDir):
        # https://stackoverflow.com/questions/70928978/sftp-how-to-list-large-of-files
        # May want to start here next, as I'm not making much progress, and removing a ton of my files just doesn't seem useful
        nextFile = os.path.join(currentDir, entry.filename)
        printHelper(tdebugger, f'Reached File: {nextFile}')

        mode = entry.st_mode
        if S_ISDIR(mode):
            # todo: may need to see if there is a safer way to join these 2, as \\ may not be safe to use for all os's
            if (tos == "win"):
                scanRemotely(sftp, currentDir + "\\" + entry.filename, root, tab + 1, tos, inputConfig)
            elif (tos == "linux"):
                scanRemotely(sftp, currentDir + "/" + entry.filename, root, tab + 1, tos, inputConfig)
            else:
                print(tos + " not supported. Only 'win' or 'linux' are supported.")
                exit()
        
            if not isRoot and len(sftp.listdir_attr(currentDir)) == 0:
                removedFile, inputConfig = removeFileRemotely(currentDir, sftp, inputConfig)

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
        elif userInput == "D":
            return False, False, False
        elif userInput == "A":
            print("\nABORTING...")
            exit()
        else:
            print("\nINVALID INPUT\n")


def removeFileRemotely(folderPathToRemove, sftp, inputConfig):
    printHelper(inputConfig.confirmDeleteNeeded, menuString)

    if inputConfig.skipAll:
        print(f'SKIPPED: {folderPathToRemove}:')
        return False, inputConfig

    if inputConfig.confirmDeleteNeeded:
        inputConfig.confirmDeleteNeeded, inputConfig.skipAll, inputConfig.skipNext = handleInput("DELETE EMPTY DIRECTORY?", folderPathToRemove)

    if not inputConfig.skipNext:
        sftp.rmdir(folderPathToRemove)
        printHelper(not inputConfig.confirmDeleteNeeded, f'DELETED {folderPathToRemove}')
        return True, inputConfig
    
    return False, inputConfig
    

# parse all arguments into pre-defined variables
tdirectory, tquieter, tdebugger, tremote, tos = parseAllArgs(args)

printHelper(tdebugger, 'Starting Program..')

if tremote != None:
    scanDirectoryRemotely(tremote, tdirectory, tdirectory, 0, tos)
else:
    # Main Logic for analyzing directory
    raise Exception("NOT IMPLEMENTED - scanDirectory")
    # scanDirectory()

printHelper(tdebugger, 'Program Finished')

exit()