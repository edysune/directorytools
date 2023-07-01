#============================= Common Parsing Functions =============================


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
    return tdirectory

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing output keys. Is not a required field.
#Returns:
#   tdebug        a valid boolean value either True/False. If anything else is given, the value is reverted back to default
def parseDebug(args, default_debugger):
    return default_debugger

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing quiet key that contains either true/t or false/f.
#Returns:
#   tquieter        a valid boolean value either True/False. If anything else is given, the value is reverted back to default
def parseQuiet(args, default_quieter):
        return default_quieter

#Preconditions: None
#Postconditions: None
#Arguments:
#   args        a dictionary containing quiet key that contains win or linux
#Returns:
#   osType      a valid value for os types, mostly used for remote/ssh
def parseOs(args, default_os):
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
def parseSize(args, default_size):
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
#           
def parseRemote(args):
    if args["remote"] is None:
        return None

    remote = args["remote"]
    user = args["user"]
    port = args["port"]
    password = args["cred"]

    return {"remote": remote, "user": user, "port": port, "password": password}

