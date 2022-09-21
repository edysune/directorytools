$outDir = "..\\results\\"
$origDir = "..\\test_dir\\"
$dir1 = "a1"
$dir2 = "a2"

$origDir1 = $origDir + "\\" + $dir1 + "\\"
$origDir2 = $origDir + "\\" + $dir2 + "\\"

$outDir1 = $outDir + "\\" + $dir1 + "\\"
$outDir2 = $outDir + "\\" + $dir2 + "\\"

$scanFileOut1 = $dir1 + ".scan.json"
$scanFileOut2 = $dir2 + ".scan.json"

$scanFolderOut1 = "folder." + $dir1 + ".scan.json"
$scanFolderOut2 = "folder." + $dir2 + ".scan.json"

$fileDiffs = "diff.file.json"
$folderDiffs = "diff.folder.json"

.\cleanDemo.ps1
Copy-Item -Path $origDir1 -Destination $outDir1 -Recurse -Force
Copy-Item -Path $origDir2 -Destination $outDir2 -Recurse -Force
py .\scanDir.py -p $outDir1 -o $scanFileOut1
py .\scanDir.py -p $outDir2 -o $scanFileOut2
py .\compareDir.py -i $scanFileOut1 $scanFileOut2 -o $fileDiffs
py .\compareDir.py -i $scanFolderOut1 $scanFolderOut2 -o $folderDiffs
py .\mergeDir.py -i $fileDiffs

# Check directories again
py .\scanDir.py -p $outDir1 -o $scanFileOut1
py .\scanDir.py -p $outDir2 -o $scanFileOut2
py .\compareDir.py -i $scanFileOut1 $scanFileOut2 -o $fileDiffs