#!/bin/sh

echo "***************************************** MERGING ANIME (PRIMARY) *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/anime_a" "/mnt/EXAMPLE/plex/anime_a"

echo "***************************************** MERGING ANIME (SECONDARY) *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/anime_b" "/mnt/EXAMPLE/plex/anime_b"

echo "************************************* TV SHOWS (PRIMARY) *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/tv_shows_a" "/mnt/EXAMPLE/plex/tv_shows_a"

echo "***************************************** MERGING TV SHOWS (SECONDARY) *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/tv_shows_b" "/mnt/EXAMPLE/plex/tv_shows_b"

echo "***************************************** MERGING ANIMATION *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/animation" "/mnt/EXAMPLE/plex/animation"

echo "***************************************** MERGING EXERCISE VIDS *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/exercise_videos" "/mnt/EXAMPLE/plex/exercise_videos"

echo "***************************************** MERGING FOREIGN TV SHOWS *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/foreign_tv_shows" "/mnt/EXAMPLE/plex/foreign_tv_shows"

echo "***************************************** REALITY TV SHOWS *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/reality_tv" "/mnt/EXAMPLE/plex/reality_tv"
