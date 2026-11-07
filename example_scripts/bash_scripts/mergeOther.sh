#!/bin/sh

echo "***************************************** MERGING MUSIC *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/music" "/mnt/EXAMPLE/plex/music"

echo "***************************************** MERGING BACKUPS *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/backup" "/mnt/EXAMPLE/plex/backup"

echo "***************************************** MERGING LEARNING VIDEOS *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/learning_videos" "/mnt/EXAMPLE/plex/learning_videos"

echo "***************************************** MERGING LEARNING VIDEOS *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/upscale_demos" "/mnt/EXAMPLE/plex/upscale_demos"
