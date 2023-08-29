#!/bin/sh

echo "***************************************** MERGING MOVIES *****************************************"
./executeRemoteMerge.sh "/mnt/A14000/plex/movies" "/mnt/A14000/plex/movies"

echo "***************************************** MERGING HOLIDAY MOVIES *****************************************"
./executeRemoteMerge.sh "/mnt/A14000/plex/holiday_movies" "/mnt/A14000/plex/holiday_movies"

echo "***************************************** MERGING ANIME MOVIES *****************************************"
./executeRemoteMerge.sh "/mnt/A16000/plex/anime_movies" "/mnt/A16000/plex/anime_movies"

echo "***************************************** MERGING ANIMATED MOVIES *****************************************"
./executeRemoteMerge.sh "/mnt/A16000/plex/animated_movies" "/mnt/A16000/plex/animated_movies"

echo "***************************************** MERGING FOREIGN MOVIES *****************************************"
./executeRemoteMerge.sh "/mnt/A16000/plex/foreign_movies" "/mnt/A16000/plex/foreign_movies"
