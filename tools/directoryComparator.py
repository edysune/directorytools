#directoryComparator.py

import json 
import os
import argparse

# 2) Compare 2 directories against each other

#============================= DEFINE DEFAULT AND GLOBAL VARIABLES =============================
# set and initialize variables used throughout the rest of the program
default_debugger = True
default_quieter = False
default_output_folder = 'output.comp.json'

#============================= DEFINE ARGPARSE =============================
# construct the argument parser
ap = argparse.ArgumentParser()
ap.add_argument("-i", "--input", help="file name and paths to 2 input files to compare with each other. Files must match in terms of content type (folders, files, etc).", nargs=2)
ap.add_argument("-o", "--output", help=f"path and filename of output json file created. Defaults to {default_output_folder}.")
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
        return default_output_folder
    return args["output"]

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing output keys. Is not a required field.
#Returns:
#   tdebug     a folder path. Program uses default json output file if not defined
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



#============================= DRIVER START =============================

def printHelper(shouldPrint, msg):
    if shouldPrint:
        print(msg)


# parse all arguments into pre-defined variables
tinput, toutput, tdebug = parseAllArgs(args)

printHelper(tdebug, 'Starting Program..')

printHelper(tdebug, 'Program Finished')


exit()