$from=$args[0]
$to=$args[1]

$origDir1 = $from
$origDir2 = $to

$scanFileOut1 = "down.scan.json"
$scanFileOut2 = "up.scan.json"

$fileDiffs = "diff.file.json"

$remoteUserName = ""
$remotePassword = ""
$remoteDomain = ""

Remove-Item * -Include *file.json
Remove-Item * -Include *scan.json

py Documents\directorytools\Tools\scanDir.py -d $origDir1 -o $scanFileOut1
py Documents\directorytools\Tools\scanDir.py -d $origDir2 -o $scanFileOut2 -r $remoteDomain -u $remoteUserName -c $remotePassword -os "linux"
py Documents\directorytools\Tools\compareDir.py -i $scanFileOut1 $scanFileOut2 -o $fileDiffs
py Documents\directorytools\Tools\mergeDir.py -i $fileDiffs -r $remoteDomain -u $remoteUserName -c $remotePassword -mr "true"
