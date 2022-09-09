py .\searchDir.py -p ..\test_dir\a1\ -o a1out.json
py .\searchDir.py -p ..\test_dir\a2\ -o a2out.json
py .\compareDir.py -i .\a1out.json .\a2out.json -o diff.json
py .\compareDir.py -i .\folder.a1out.json .\folder.a2out.json -o diff.folder.json