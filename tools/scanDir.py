#scanDir.py

import json 
import os
import argparse
from paramiko import SSHClient
from stat import S_ISDIR, S_ISREG
from structs import *

#============================= DEFINE DEFAULT AND GLOBAL VARIABLES =============================
# set and initialize variables used throughout the rest of the program
default_debugger = False
default_quieter = True
default_folderAnalyze = True
default_output_folder = 'output.json'
default_size = "KB"
default_os = "win"

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
ap.add_argument("-c", "--cred", help="password for remote SSH. Not needed for local usage.")
ap.add_argument("-os", "--osys", help="operating system. Defaults to 'win'.")
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
    tos = parseOs(args)
    return tdirectory, toutput, tquieter, tdebugger, tfolderAnalyze, tsize, tremote, tos

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
#   args        a dictionary containing quiet key that contains win or linux
#Returns:
#   osType      a valid value for os types, mostly used for remote/ssh
def parseOs(args):
    osType = args["osys"]

    validValues = ["win", "linux"]

    if osType in validValues:
        return osType
    elif osType is None:
        return default_os
    else:
        print(f"Error: os argument {osType} not win, or linux - defaulting to {default_os}")
        return default_os


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
    password = args["cred"]


    return {"remote": remote, "user": user, "port": port, "password": password}


#============================= DRIVER START =============================

def calcSha256Locally(file):
    #  never actually use this on big files. It will literally take minutes. Not even going to attempt to support this remotely.
    calcSha = False
    if (calcSha):
        with open(file,"rb") as f:
            bytes = f.read() # read entire file as bytes
            readable_hash = hashlib.sha256(bytes).hexdigest()
            print(readable_hash)
            return readable_hash
    return None

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

            fileSha256 = calcSha256Locally(nextFile)
            fileObj = file(currentDir, fname, root, tab)
            fileStruct.addFile(fileObj)
            folderStruct.addFile(fileObj)

def scanDirectoryRemotely(remoteInput, currentDir, root, fileStruct, tab, tos):
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
    scanRemotely(sftp, currentDir, root, fileStruct, tab, tos)

    printHelper(tdebugger, "Closing connections...")
    sftp.close()
    ssh.close()

def scanRemotely(sftp, currentDir, root, fileStruct, tab, tos):
    for entry in sftp.listdir_attr(currentDir):
        # https://stackoverflow.com/questions/70928978/sftp-how-to-list-large-of-files
        # May want to start here next, as I'm not making much progress, and removing a ton of my files just doesn't seem useful
        nextFile = os.path.join(currentDir, entry.filename)
        printHelper(tdebugger, f'Reached File: {nextFile}')

        mode = entry.st_mode
        if S_ISDIR(mode):
            # todo: may need to see if there is a safer way to join these 2, as \\ may not be safe to use for all os's
            if (tos == "win"):
                scanRemotely(sftp, currentDir + "\\" + entry.filename, root, fileStruct, tab + 1, tos)
            elif (tos == "linux"):
                scanRemotely(sftp, currentDir + "/" + entry.filename, root, fileStruct, tab + 1, tos)
            else:
                print(tos + " not supported. Only 'win' or 'linux' are supported.")
                exit()
            
        elif S_ISREG(mode):
            fileObj = file(currentDir, entry.filename, root, tab, entry.st_size, tos)
            fileStruct.addFile(fileObj)


# parse all arguments into pre-defined variables
tdirectory, toutput, tquieter, tdebugger, tfolderAnalyze, tsize, tremote, tos = parseAllArgs(args)

globalSizeConversion = tsize

fileStruct = fileStructure(tos)
folderStruct = folderStructure()

printHelper(tdebugger, 'Starting Program..')

if tremote != None:
    scanDirectoryRemotely(tremote, tdirectory, tdirectory, fileStruct, 0, tos)
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