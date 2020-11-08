import json
import argparse
import os 

#============================= DEFINE ARGPARSE =============================

ap = argparse.ArgumentParser()
ap.add_argument("-n", "--new", help="Creates a new configuration to fill out, and execute.")
ap.add_argument("-e", "--execute", help="Executes configuration file.")
ap.add_argument("-v", "--verbose", help="This argument turns debugging prints on so you can see more information about the utility running.", action='store_true')
args = vars(ap.parse_args())

#============================= DEFINE GLOBALS =============================

DEFAULT_JSON_WRITE_INDENT = 4
DEFAULT_DIRECTORY_TEMPLATE = {
    "os": "[windows/linux]",
    "directory": "[directory/path]",
    "search_multiple_drives": False,
    "type": "[local|remote]",
    "username": "<only remote - not needed for local usage>",
    "[password|key]": "<only remote - not needed for local usage>",
    "file_size": "[b|kb|gb]"
}

#============================= MAIN - Either Create a file or Execute a Config =============================


def analyzeArgs(args):
    if args["new"] is not None:
        createConfig(args["new"])
        return
    elif args["execute"] is not None:
        executeConfiguration(args["execute"])
    else:
        print("Error: Create a file, or execute one already created.")

def createConfig(fileName):
    init_directory_template = [DEFAULT_DIRECTORY_TEMPLATE]

    if isVerbose():
        print(f"Writing Default Config to file '{fileName}'")

    #write default json template for config to file
    with open(fileName, "w") as f:
        f.write(json.dumps(init_directory_template, indent=DEFAULT_JSON_WRITE_INDENT))


def executeConfiguration(configFile):

    output = "output.txt"
    fout = open(output, "w")

    #load json from configuration to file
    with open(configFile, "r") as f:
        all_dirs = json.load(f)

    for dir_to_execute in all_dirs:
        isValidOS, osType = validateOS(dir_to_execute)
        isValidDir, directoryPath = validateDirectory(dir_to_execute)
        isValidType, executeType = validateType(dir_to_execute)
        isValidSize, fileSize = validateSize(dir_to_execute)

        if not isValidType or not isValidOS or not isValidDir or not isValidSize:
            print(f"Error: Configuration is either missing or has invalid fields for:\nOS\t\t{osType}:{isValidOS}\nDirectory\t{directoryPath}:{isValidDir}\nExecute Type\t{executeType}:{isValidType}\nFile Size\t{fileSize}:{isValidSize}")
            continue
        
        if executeType == "local":
            

            if searchMultipleDrives(dir_to_execute):
                print("Multiple Searches not implemented...")
                if osType == "windows":
                    drives = getAvailableWindowsDrives()
                    print(drives)
                else:


                #get a list of all other drives
                #check each drive for this, starting from root if it's not a 
            else:
                #should not be a file that exists - if it's a file, let the user know to correct this and give a folder instead
                if os.path.isfile(directoryPath):
                    print(f"Error: {directoryPath} is a file, which should be a folder instead. Please give a valid folder in place.")
                    continue
                
                #should exist as a folder - if it's not a folder then let the user know to correct this and give a folder instead
                if not os.path.isdir(directoryPath):
                    print(f"Error: {directoryPath} is NOT a folder. Please give a valid folder in place.")
   
                #consume the entire directories recursively
                consumeEntireDirectory(directoryPath, fout)
                

    

    fout.close()


def consumeEntireDirectory(directoryPath, fout):
    fout.write(f"\n{directoryPath}\n")
    #go through each file - print out file name and space used
    for filename in os.listdir(directoryPath):
        if os.path.isfile(os.path.join(directoryPath, filename)):
            #print(f"{filename} is a file")
            size = os.path.getsize(os.path.join(directoryPath, filename))
            fout.write(f"{filename} {size}\n")

    #go through each folder, and call this recursively
    for filename in os.listdir(directoryPath):
        if os.path.isdir(os.path.join(directoryPath, filename)):
            #print(f"{filename} is a folder")
            consumeEntireDirectory(os.path.join(directoryPath, filename), fout)


def getAvailableWindowsDrives():
    #dirty solution - coult use instead:
    # >>> import psutil
    # >>> psutil.disk_partitions()
    return ['%s:' % d for d in string.ascii_uppercase if os.path.exists('%s:' % d)]


#============================= ARGPARSE - VALIDATION FUNCTIONS =============================


def validateOS(dir_to_execute):
    if dir_to_execute.get("os") is None:
        return False, None
    if dir_to_execute["os"] != "windows" and dir_to_execute["os"] != "linux":
        return False, None
    return True, dir_to_execute["os"]
    
def validateDirectory(dir_to_execute):
    if dir_to_execute.get("directory") is None:
        return False, None
    return True, dir_to_execute["directory"]

def validateType(dir_to_execute):
    if dir_to_execute.get("type") is None:
        return False, None
    if dir_to_execute["type"] != "local" and dir_to_execute["type"] != "remote":
        return False, None
    return True, dir_to_execute["type"]

def validateUsername(dir_to_execute):
    #not done
    return False

def validatePasswordOrKey(dir_to_execute):
    #not done
    return False

def validateSize(dir_to_execute):
    if dir_to_execute.get("file_size") is None:
        return False, None
    if dir_to_execute["file_size"] != "b" and dir_to_execute["file_size"] != "kb" and dir_to_execute["file_size"] != "gb":
        return False, None
    return True, dir_to_execute["file_size"]

def searchMultipleDrives(dir_to_execute):
    if dir_to_execute.get("search_multiple_drives") is None:
        return False
    if dir_to_execute["search_multiple_drives"] != True:
        return False
    return True


def isVerbose():
    return args["verbose"]

analyzeArgs(args)
