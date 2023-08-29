
write-host "***************************************** MERGING ANIME (PRIMARY) *****************************************"
./executeRemoteMerge.ps1  "T:\Plex\Anime" "/mnt/A14002/plex/anime_a"

write-host "***************************************** MERGING ANIME (SECONDARY) *****************************************"
./executeRemoteMerge.ps1  "F:\PLEX\Anime" "/mnt/A16000/plex/anime_b"

write-host "************************************* TV SHOWS (PRIMARY) *****************************************"
./executeRemoteMerge.ps1  "U:\Plex\TV Shows" "/mnt/A14001/plex/tv_shows_a"

write-host "***************************************** MERGING TV SHOWS (SECONDARY) *****************************************"
./executeRemoteMerge.ps1  "D:\Plex\TV Shows" "/mnt/A18000/plex/tv_shows_b"

write-host "***************************************** MERGING ANIMATION *****************************************"
./executeRemoteMerge.ps1  "D:\Plex\Animation" "/mnt/A18000/plex/animation"

write-host "***************************************** MERGING EXERCISE VIDS *****************************************"
./executeRemoteMerge.ps1  "F:\PLEX\Exercise Videos" "/mnt/A16000/plex/exercise_videos"

write-host "***************************************** MERGING FOREIGN TV SHOWS *****************************************"
./executeRemoteMerge.ps1  "F:\PLEX\Foreign TV Shows" "/mnt/A16000/plex/foreign_tv_shows"

write-host "***************************************** REALITY TV SHOWS *****************************************"
./executeRemoteMerge.ps1  "F:\PLEX\Reality TV" "/mnt/A16000/plex/reality_tv"
