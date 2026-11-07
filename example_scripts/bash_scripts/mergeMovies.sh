#!/bin/sh

echo "***************************************** MERGING MOVIES *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/movies" "/mnt/EXAMPLE/plex/movies"

echo "***************************************** MERGING HOLIDAY MOVIES *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/holiday_movies" "/mnt/EXAMPLE/plex/holiday_movies"

echo "***************************************** MERGING ANIME MOVIES *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/anime_movies" "/mnt/EXAMPLE/plex/anime_movies"

echo "***************************************** MERGING ANIMATED MOVIES *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/animated_movies" "/mnt/EXAMPLE/plex/animated_movies"

echo "***************************************** MERGING FOREIGN MOVIES *****************************************"
./executeRemoteMerge.sh "/mnt/EXAMPLE/plex/foreign_movies" "/mnt/EXAMPLE/plex/foreign_movies"
