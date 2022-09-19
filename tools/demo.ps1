.\cleanDemo.ps1
py .\scanDir.py -p ..\test_dir\a1\ -o a1.scan.json
py .\scanDir.py -p ..\test_dir\a2\ -o a2.scan.json
py .\compareDir.py -i .\a1.scan.json .\a2.scan.json -o diff.file.json
py .\compareDir.py -i .\folder.a1.scan.json .\folder.a2.scan.json -o diff.folder.json