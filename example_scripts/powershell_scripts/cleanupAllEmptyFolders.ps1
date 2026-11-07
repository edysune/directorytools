write-host "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ CLEANING UP EMPTY FOLDERS @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@"

$paths = @("/mnt/EXAMPLE/plex/tv_shows_a", "/mnt/EXAMPLE/plex/anime_a", "/mnt/EXAMPLE/plex/anime_b", "/mnt/EXAMPLE/plex/tv_shows_b", "/mnt/EXAMPLE/plex/animation", "/mnt/EXAMPLE/plex/exercise_videos",
    "/mnt/EXAMPLE/plex/foreign_tv_shows", "/mnt/EXAMPLE/plex/reality_tv", "/mnt/EXAMPLE/plex/music", "/mnt/EXAMPLE/plex/backup", "/mnt/EXAMPLE/plex/learning_videos", "/mnt/EXAMPLE/plex/upscale_demos",
    "/mnt/EXAMPLE/plex/movies", "/mnt/EXAMPLE/plex/holiday_movies", "/mnt/EXAMPLE/plex/anime_movies", "/mnt/EXAMPLE/plex/animated_movies", "/mnt/EXAMPLE/plex/foreign_movies")

foreach ($path in $paths) {
    write-host "***************************************** " + $path + " *****************************************"
    ./executeRemoteCleanup.ps1  $path
}