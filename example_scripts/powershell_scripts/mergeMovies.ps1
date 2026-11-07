write-host "***************************************** MERGING MOVIES *****************************************"
./executeRemoteMerge.ps1  "P:\PLEX\Movies" "/mnt/EXAMPLE/plex/movies"

write-host "***************************************** MERGING HOLIDAY MOVIES *****************************************"
./executeRemoteMerge.ps1  "P:\PLEX\Holiday Movies" "/mnt/EXAMPLE/plex/holiday_movies"

write-host "***************************************** MERGING ANIME MOVIES *****************************************"
./executeRemoteMerge.ps1  "P:\PLEX\Anime Movies" "/mnt/EXAMPLE/plex/anime_movies"

write-host "***************************************** MERGING ANIMATED MOVIES *****************************************"
./executeRemoteMerge.ps1  "P:\PLEX\Animated Movies" "/mnt/EXAMPLE/plex/animated_movies"

write-host "***************************************** MERGING FOREIGN MOVIES *****************************************"
./executeRemoteMerge.ps1  "P:\PLEX\Foreign Movies" "/mnt/EXAMPLE/plex/foreign_movies"
