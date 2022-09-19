$outDir = "..\\results\\"

Remove-Item * -Include *.json
Remove-Item -Recurse -Force $outDir -ErrorAction SilentlyContinue
