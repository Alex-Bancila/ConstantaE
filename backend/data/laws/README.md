# Law texts

Put the consolidated text (*forma consolidată*) of each law here as a UTF-8 `.txt`
file, one file per law, named after the law:

- `oug-34-2014.txt`: consumer rights in distance contracts
- `og-21-1992.txt`: consumer protection

Source: [legislatie.just.ro](https://legislatie.just.ro/). Then run, from the
`backend` folder:

```bash
python -m app.ai.rag.ingest
```
