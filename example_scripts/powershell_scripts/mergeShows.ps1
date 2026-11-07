
write-host "***************************************** MERGING ANIME (PRIMARY) *****************************************"
./executeRemoteMerge.ps1  "P:\Plex\Anime" "/mnt/EXAMPLE/plex/anime_a"

write-host "***************************************** MERGING ANIME (SECONDARY) *****************************************"
./executeRemoteMerge.ps1  "P:\PLEX\Anime" "/mnt/EXAMPLE/plex/anime_b"

write-host "************************************* TV SHOWS (PRIMARY) *****************************************"
./executeRemoteMerge.ps1  "P:\Plex\TV Shows" "/mnt/EXAMPLE/plex/tv_shows_a"

write-host "***************************************** MERGING TV SHOWS (SECONDARY) *****************************************"
./executeRemoteMerge.ps1  "P:\Plex\TV Shows" "/mnt/EXAMPLE/plex/tv_shows_b"

write-host "***************************************** MERGING ANIMATION *****************************************"
./executeRemoteMerge.ps1  "P:\Plex\Animation" "/mnt/EXAMPLE/plex/animation"

write-host "***************************************** MERGING EXERCISE VIDS *****************************************"
./executeRemoteMerge.ps1  "P:\PLEX\Exercise Videos" "/mnt/EXAMPLE/plex/exercise_videos"

write-host "***************************************** MERGING FOREIGN TV SHOWS *****************************************"
./executeRemoteMerge.ps1  "P:\PLEX\Foreign TV Shows" "/mnt/EXAMPLE/plex/foreign_tv_shows"

write-host "***************************************** REALITY TV SHOWS *****************************************"
./executeRemoteMerge.ps1  "P:\PLEX\Reality TV" "/mnt/EXAMPLE/plex/reality_tv"
