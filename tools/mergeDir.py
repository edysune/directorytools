#mergeDir.py
# script that merges differences

import json 
import os
import argparse

#============================= DEFINE DEFAULT AND GLOBAL VARIABLES =============================
# set and initialize variables used throughout the rest of the program
defaultDebugger = False
defaultForce = False
defaultQuieter = True
validTypes = ["file"]

#============================= DEFINE ARGPARSE =============================
# construct the argument parser
ap = argparse.ArgumentParser()
ap.add_argument("-i", "--input", help="path and filename of the diff json object", nargs=1)
ap.add_argument("-f", "--force", help="true/false or t/f supported. This argument forces merge to do a complete sync, including removing files. Do not use for partial merges.")
ap.add_argument("-r", "--remote", help="<URL>:<PORT>")
ap.add_argument("-d", "--debug", help="true/false or t/f supported. This argument turns debugging prints on/off, which gives slightly more information about program as it runs.")
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
        print("-p <DIFF INPUT PATH + FILENAME> is not defined\nPlease see HELP screen for more information about how to use this program.")
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
#   args        a dictionary containing output keys. Is not a required field.
#Returns:
#   
def parseRemote(args):
    if args["remote"] is None:
        return None
    return args["remote"]    

#============================= DRIVER START =============================

def printHelper(shouldPrint, msg):
    if shouldPrint:
        print(msg)

def loadJsonFile(file):
    f = open(file,)
    data = json.load(f)

    res = []
    fileType = data['metadata'].lower()
    fileRoot = data['root']

    if fileType != "file" and fileType != "folder":
        print(f"ERROR - file type {fileType} is neither file nor folder. Exiting program..")
        exit()

    for file in data['files']:
        res.append(FileComparableObj(file, fileType))
    return fileType, res, fileRoot

def enforceFileType(ftype):
    if ftype not in validTypes :
        print(f"File type {ftype} is not valid. Program exiting...")
        exit()


# parse all arguments into pre-defined variables
tinput, tforce, tremote, tdebug = parseAllArgs(args)

printHelper(tdebug, 'Starting Program..')

loadJsonFile(tinput)
# enforceFileType(ftype1, ftype2, tinput)

printHelper(tdebug, 'Program Finished')

exit()