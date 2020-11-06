import json
import argparse


#============================= DEFINE ARGPARSE =============================

ap = argparse.ArgumentParser()
ap.add_argument("-n", "--new", help="Creates a new configuration to fill out, and execute.")
ap.add_argument("-e", "--execute", help="Executes configuration file.")
ap.add_argument("-v", "--verbose", help="This argument turns debugging prints on so you can see more information about the utility running.")
args = vars(ap.parse_args())


#============================= MAIN - Either Create a file or Execute a Config =============================


def analyzeArgs(args):
    if args["verbose"] is not None:
        print("Turning verbose on..")
    if args["new"] is not None:
        createConfig(args["new"])
        return
    if args["execute"] is not None:
        print(f"Executing {execute}")
    else:
        print("Error: Create a file, or execute one already created.")

def createConfig(fileName):
    print(f"Creating Config File... {fileName}")
    
    init_directory_template = [{
        "directory": "",
        "type": "[local|remote]",
        "username": "<only remote - not needed for local usage>",
        "password": "<only remote - not needed for local usage>",
        "filesize": "[b|kb|gb]"
    }]

    # convert into JSON:
    f = open(fileName, "w")
    f.write(json.dumps(init_directory_template, indent=4))
    f.close()


analyzeArgs(args)
