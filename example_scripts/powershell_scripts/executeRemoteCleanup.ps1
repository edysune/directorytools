$path=$args[0]

$remoteUserName = ""
$remotePassword = ""
$remoteDomain = ""

py Documents\directorytools\Tools\cleanUpDir.py -d $path -r $remoteDomain -u $remoteUserName -c $remotePassword -os "linux"
