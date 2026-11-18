# Law texts

Put the consolidated text (*forma consolidată*) of each law here as a UTF-8 `.txt`
file, one file per law, named after the law:

- `oug-34-2014.txt`: consumer rights in distance contracts - https://legislatie.just.ro/Public/DetaliiDocumentAfis/257171
  - Published: Monitorul Oficial nr. 427, 11 June 2014
  - Latest incorporated update: 28 May 2022 (OUG 58/2022)
- `og-21-1992.txt`: consumer protection - https://legislatie.just.ro/Public/DetaliiDocumentAfis/269119
  - Republished: Monitorul Oficial nr. 208, 28 March 2007
  - Latest incorporated amendment noted in the source: 7 September 2015 (OG 37/2015)


Source: [legislatie.just.ro](https://legislatie.just.ro/). Then run, from the
`backend` folder:

```bash
python -m app.ai.rag.ingest
```

The ingestion command uses `intfloat/multilingual-e5-small` to create
multilingual article embeddings and stores them in PostgreSQL with pgvector.
Set `DATABASE_URL` before running it.
