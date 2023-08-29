write-host "***************************************** MERGING MOVIES *****************************************"
./executeRemoteMerge.ps1  "I:\PLEX\Movies" "/mnt/A14000/plex/movies"

write-host "***************************************** MERGING HOLIDAY MOVIES *****************************************"
./executeRemoteMerge.ps1  "I:\PLEX\Holiday Movies" "/mnt/A14000/plex/holiday_movies"

write-host "***************************************** MERGING ANIME MOVIES *****************************************"
./executeRemoteMerge.ps1  "F:\PLEX\Anime Movies" "/mnt/A16000/plex/anime_movies"

write-host "***************************************** MERGING ANIMATED MOVIES *****************************************"
./executeRemoteMerge.ps1  "F:\PLEX\Animated Movies" "/mnt/A16000/plex/animated_movies"

write-host "***************************************** MERGING FOREIGN MOVIES *****************************************"
./executeRemoteMerge.ps1  "F:\PLEX\Foreign Movies" "/mnt/A16000/plex/foreign_movies"
