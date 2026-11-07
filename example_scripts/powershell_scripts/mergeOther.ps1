
write-host "***************************************** MERGING MUSIC *****************************************"
./executeRemoteMerge.ps1  "P:\Music" "/mnt/EXAMPLE/plex/music"

write-host "***************************************** MERGING BACKUPS *****************************************"
./executeRemoteMerge.ps1  "P:\backup" "/mnt/EXAMPLE/plex/backup"

write-host "***************************************** MERGING LEARNING VIDEOS *****************************************"
./executeRemoteMerge.ps1  "P:\Learning Videos" "/mnt/EXAMPLE/plex/learning_videos"

write-host "***************************************** MERGING LEARNING VIDEOS *****************************************"
./executeRemoteMerge.ps1  "P:\Upscale Demos" "/mnt/EXAMPLE/plex/upscale_demos"
