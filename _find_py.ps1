Get-ChildItem -Path 'C:\Users\AppData\Local\Programs\Python' -Recurse -Filter 'python.exe' -ErrorAction SilentlyContinue | Select-Object -First 5 FullName, Length
