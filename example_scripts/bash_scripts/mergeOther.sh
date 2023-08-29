#!/bin/sh

echo "***************************************** MERGING MUSIC *****************************************"
./executeRemoteMerge.sh "/mnt/A14000/plex/music" "/mnt/A14000/plex/music"

echo "***************************************** MERGING BACKUPS *****************************************"
./executeRemoteMerge.sh "/mnt/A14000/plex/backup" "/mnt/A14000/plex/backup"

echo "***************************************** MERGING LEARNING VIDEOS *****************************************"
./executeRemoteMerge.sh "/mnt/A14000/plex/learning_videos" "/mnt/A14000/plex/learning_videos"

echo "***************************************** MERGING LEARNING VIDEOS *****************************************"
./executeRemoteMerge.sh "/mnt/A14000/plex/upscale_demos" "/mnt/A14000/plex/upscale_demos"
