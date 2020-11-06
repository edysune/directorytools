import json
import argparse


#============================= DEFINE ARGPARSE =============================

ap = argparse.ArgumentParser()
ap.add_argument("-n", "--new", help="Creates a new configuration to fill out, and execute.")
ap.add_argument("-e", "--execute", help="Executes configuration file.")
ap.add_argument("-v", "--verbose", help="This argument turns debugging prints on so you can see more information about the utility running.")
args = vars(ap.parse_args())

#============================= DEFINE GLOBALS =============================
VERBOSE = False
DEFAULT_JSON_WRITE_INDENT = 4
DEFAULT_DIRECTORY_TEMPLATE = {
    "os": "[windows/linux]",
    "directory": "[directory/path]",
    "type": "[local|remote]",
    "username": "<only remote - not needed for local usage>",
    "[password|key]": "<only remote - not needed for local usage>",
    "filesize": "[b|kb|gb]"
}

#============================= MAIN - Either Create a file or Execute a Config =============================


def analyzeArgs(args):
    if args["verbose"] is not None:
        print("Turning verbose on..")
        VERBOSE = True
    if args["new"] is not None:
        createConfig(args["new"])
        return
    if args["execute"] is not None:
        print(f"Executing {execute}")
    else:
        print("Error: Create a file, or execute one already created.")

def createConfig(fileName):
    init_directory_template = [DEFAULT_DIRECTORY_TEMPLATE]

    # convert into JSON:
    if VERBOSE:
        print(f"Writing Default Config to file '{fileName}'")
    f = open(fileName, "w")
    f.write(json.dumps(init_directory_template, indent=DEFAULT_JSON_WRITE_INDENT))
    f.close()


analyzeArgs(args)
