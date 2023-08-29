#!/bin/sh

echo "***************************************** MERGING ANIME (PRIMARY) *****************************************"
./executeRemoteMerge.sh "/mnt/A14002/plex/anime_a" "/mnt/A14002/plex/anime_a"

echo "***************************************** MERGING ANIME (SECONDARY) *****************************************"
./executeRemoteMerge.sh "/mnt/A16000/plex/anime_b" "/mnt/A16000/plex/anime_b"

echo "************************************* TV SHOWS (PRIMARY) *****************************************"
./executeRemoteMerge.sh "/mnt/A14001/plex/tv_shows_a" "/mnt/A14001/plex/tv_shows_a"

echo "***************************************** MERGING TV SHOWS (SECONDARY) *****************************************"
./executeRemoteMerge.sh "/mnt/A18000/plex/tv_shows_b" "/mnt/A18000/plex/tv_shows_b"

echo "***************************************** MERGING ANIMATION *****************************************"
./executeRemoteMerge.sh "/mnt/A18000/plex/animation" "/mnt/A18000/plex/animation"

echo "***************************************** MERGING EXERCISE VIDS *****************************************"
./executeRemoteMerge.sh "/mnt/A16000/plex/exercise_videos" "/mnt/A16000/plex/exercise_videos"

echo "***************************************** MERGING FOREIGN TV SHOWS *****************************************"
./executeRemoteMerge.sh "/mnt/A16000/plex/foreign_tv_shows" "/mnt/A16000/plex/foreign_tv_shows"

echo "***************************************** REALITY TV SHOWS *****************************************"
./executeRemoteMerge.sh "/mnt/A16000/plex/reality_tv" "/mnt/A16000/plex/reality_tv"
