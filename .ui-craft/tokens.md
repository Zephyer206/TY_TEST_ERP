# Current interface tokens

Source: `frontend/src/styles/workbench.css`. Reuse these tokens rather than introducing a second theme.

- Accent: `--zephyr-primary` #5665a8; hover #43538f; soft #eef0f8.
- Text: ink #252b3b; body #414a5c; muted #687387.
- Surfaces: white; canvas #f3f4f7; muted #f7f8fb.
- Borders: #dde2eb; soft #ebedf2.
- Typography: Segoe UI, PingFang SC, Microsoft YaHei; system monospace for technical values. Body 13px; supporting text 12px; page heading 22px.
- Spacing: 4, 8, 12, 16, 20, 24px. Desktop controls 32px; dense table rows 36px.
- Radius: controls 6px; tables/panels 8px; dialogs 12px.
- Motion: mouse press 130ms; custom ease-out cubic-bezier(0.16, 1, 0.3, 1). Navigation and keyboard actions remain immediate. Honor reduced motion.
