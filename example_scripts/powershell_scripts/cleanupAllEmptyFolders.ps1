write-host "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ CLEANING UP EMPTY FOLDERS @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@"

$paths = @("/mnt/A14001/plex/tv_shows_a", "/mnt/A14002/plex/anime_a", "/mnt/A16000/plex/anime_b", "/mnt/A18000/plex/tv_shows_b", "/mnt/A18000/plex/animation", "/mnt/A16000/plex/exercise_videos",
    "/mnt/A16000/plex/foreign_tv_shows", "/mnt/A16000/plex/reality_tv", "/mnt/A14000/plex/music", "/mnt/A14000/plex/backup", "/mnt/A14000/plex/learning_videos", "/mnt/A14000/plex/upscale_demos",
    "/mnt/A14000/plex/movies", "/mnt/A14000/plex/holiday_movies", "/mnt/A16000/plex/anime_movies", "/mnt/A16000/plex/animated_movies", "/mnt/A16000/plex/foreign_movies")

foreach ($path in $paths) {
    write-host "***************************************** " + $path + " *****************************************"
    ./executeRemoteCleanup.ps1  $path
}