import uvicorn, sys
sys.path.insert(0, '.')
uvicorn.run('main:app', host='0.0.0.0', port=8000, reload=False)
