#!/bin/sh

from=$2
to=$1

toScan="to.scan.json"
fromScan="from.scan.json"
fileDiffs="diff.file.json"

remoteUserName=""
remotePassword=""
remoteDomain=""

rm -f *file.json
rm -f *scan.json

python directorytools/tools/scanDir.py -d $to -o $toScan -os "linux"
python directorytools/tools/scanDir.py -d $from -o $fromScan -r $remoteDomain -u $remoteUserName -c $remotePassword -os "linux"
python directorytools/tools/compareDir.py -i $fromScan $toScan -o $fileDiffs
python directorytools/tools/mergeDir.py -i $fileDiffs -r $remoteDomain -u $remoteUserName -c $remotePassword -mr "false" --confirmMerge "false" --confirmDelete "false"
