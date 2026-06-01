$ErrorActionPreference = 'SilentlyContinue'
$py = "C:\Users\AppData\Local\Programs\Python\Python313\python.exe"
$script = "import uvicorn, sys; sys.path.insert(0,'.'); uvicorn.run('main:app',host='0.0.0.0',port=8000,reload=False)"
$p = Start-Process -FilePath $py -ArgumentList "-X utf8", "-c", $script -PassThru -WindowStyle Hidden
if ($p) { Write-Host "Server started PID: $($p.Id)" } else { Write-Host "Failed" }
