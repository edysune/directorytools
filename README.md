# Directory Tools
Tools comparing directories. This mainly was built to solve issues with keeping manual back-ups. Files will sometimes drift (renamed, missing, etc), and back-ups are sometimes really difficult to go through, especially with larger drives. The ultimate goal of this project is to make a client/server that will continuously check on changes made to backups, and to sync missing files.

# setup
General install includes:
1. Download python 3.10+
2. Add scripts folder in `C:\Users\<user>\AppData\Local\Programs\Python` to the environment variables for pip access

# scripts
See `example_scripts` for examples of working scripts both in powershell and bash formats. Scripts will need to be placed in the directory right outside of where this README.md file is:

```
    <put_example_script_here>\directorytools\tools
```

Note that these may need modifications for paths for your own directory system. The main script `executeRemoteMerge` has required userName, password and domain that will need to be set. Domains will need to be added in the `etc/hosts` file, which depends based 

# scanDir
Basic tool that generates a recursive list of files given a folder path parameter. This works both locally and remotely (using SSH username + password), and works with both Windows and Linux OS's. By default, scanDir operating system is set to `win`, which may need to set via commandline flags. Example of usage:

```
    py .\scanDir.py -p ..\test_dir\a1\ -os "linux"
```

This tool generates a .json file output, which is used for input for following tools. The .json file contains raw information that was scanned from the root directory given.

# compareDir
Compares the output generated by scanDir. Example of usage:
```
    py .\scanDir.py -p ..\test_dir\a1\ -o output1.json -os "linux"
    py .\scanDir.py -p ..\test_dir\a2\ -o output2.json -os "win"
    py .\compareDir.py -i .\output1.json .\output2.json -o output.diff.json
```

compareDir is designed to work with outputs that have different operating systems as seen in the example above. Output from compareDir contains list of files that are either missing or extraneous from either root directories.

In the example above,`output1.json` is the source-of-truth since it's the first parameter of compareDir. This means that the output of compareDir will display files that need `output2.json` is missing, or that `output2.json` needs to remove in order to match `output1.json` exactly. Overall, these tools are designed to keep directories updated and matching from a single source-of-truth.

# mergeDir
Merges will attempt to merge differences between 2 file systems, copying strictly from the source-of-truth to another directory. Most combination of OS (windows/linux) and remote/not remote should work. Example of usage:

```
    py .\scanDir.py -p ..\test_dir\a1\ -o to.json -os "linux"
    py .\scanDir.py -p /test/test_dir/a2/ -o from.json -os "win" -r test.com -u myusername -c somepassword123 -os "win"
    py .\compareDir.py -i .\output1.json .\from.json -o to.diff.json
    py .\mergeDir.py -i output.diff.json -r test.com -u myusername -c somepassword123 -os "linux" -mr "false" --confirmMerge "true" --confirmDelete "true"
```

Above describes `..\test_dir\a1\`, a local linux path on the machine that is currently running the script, copying and deleting it's files to match `/test/test_dir/a2/`, a windows path accessible via SSH. Only `..\test_dir\a1\` will change,  since `--confirmMerge "true" --confirmDelete "true"` are set, user must manually approve of each file change (recommened until your scripts are working to avoid unwanted loss of data).

# cleanUpDir
Removes empty directories recursively given a source path. May not be fully working with all different flag combinations (remote vs os), but should have some os support (Windows) as well as remote support (SSH + UserPassword) Example of usage:

```
    py .\cleanUpDir.py -d $path -r 192.168.0.55 -u myusername -c somepassword123 -os "win"
```

# trouble-shooting tips

## Cannot run scripts (linux)
Scripts provided may have had line-endings added, use following command in the same directory of bash scripts to remove windows line-endings:
```
    sed -i -e 's/\r$//' *.sh
```

## Scripts error: <domain> not found in known_hosts
May need to add your domain to the `known_hosts`. The easiest way would be to just ssh manually before running the scripts.
