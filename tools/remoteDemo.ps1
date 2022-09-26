$outDir = "..\results"
$origDir1 = "T:\???"
$origDir2 = "H:\???"

$scanFileOut1 = "a.scan.json"
$scanFileOut2 = "b.scan.json"

$fileDiffs = "diff.file.json"

.\clean.ps1
New-Item -Path $outDir -ItemType Directory

py .\scanDir.py -d $origDir1 -o $scanFileOut1 -r "a.int" -u "dobit"
py .\scanDir.py -d $origDir2 -o $scanFileOut2 -r "b.int" -u "robit"
py .\compareDir.py -i $scanFileOut1 $scanFileOut2 -o $fileDiffs