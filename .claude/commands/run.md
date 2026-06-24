# run

Start the full stack (API + UI) in hot-reload mode.

```bash
make up
```

- API → http://localhost:8000
- UI  → http://localhost:3000

`app/` and `prompts/` are volume-mounted; backend changes reload automatically. A rebuild (`make build`) is only needed when `requirements.txt` or the Dockerfile changes.
