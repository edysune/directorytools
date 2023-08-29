
write-host "***************************************** MERGING MUSIC *****************************************"
./executeRemoteMerge.ps1  "H:\Music" "/mnt/A14000/plex/music"

write-host "***************************************** MERGING BACKUPS *****************************************"
./executeRemoteMerge.ps1  "H:\backup" "/mnt/A14000/plex/backup"

write-host "***************************************** MERGING LEARNING VIDEOS *****************************************"
./executeRemoteMerge.ps1  "H:\Learning Videos" "/mnt/A14000/plex/learning_videos"

write-host "***************************************** MERGING LEARNING VIDEOS *****************************************"
./executeRemoteMerge.ps1  "H:\Upscale Demos" "/mnt/A14000/plex/upscale_demos"
