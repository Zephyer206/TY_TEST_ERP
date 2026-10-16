# Mobile Companion Quickstart

## Local development

```powershell
cd mobile-h5
npm install
$env:VITE_DEV_API_TARGET = 'http://127.0.0.1:8000'
npm run dev -- --host 0.0.0.0 --port 8080
```

Open `http://127.0.0.1:8080/login`. The mobile app uses the same local backend under `/api/v1`; do not put credentials in source files.

## Build

```powershell
cd mobile-h5
npm run build
```

## Runtime routes

- `/query`: price and part lookup
- `/production`: read-only production status
- `/delivery`: inventory and packaging/shipping lookup
- `/scan`: QR entry point, currently manual fallback

The `/report` route remains reserved for the production-session phase and is intentionally not exposed in the current mobile navigation.
