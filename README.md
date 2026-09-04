# Investment Research Platform

A production-oriented personal investment research journal built with Python 3.11+, Streamlit, Supabase PostgreSQL, pandas, Plotly, and YAML-driven research frameworks.

## Features

- Company CRUD and search
- Structured investment research framework
- Versioned analysis workflow
- Valuation scenarios with expected return logic
- Dashboard with filters and metric views
- YAML configuration for research sections and questions
- Sample META company and training analysis

## Local setup

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the environment example:
   ```bash
   copy .env.example .env
   ```
4. Populate your local secrets or environment variables with your Supabase URL and key.
5. Start the app:
   ```bash
   streamlit run app.py
   ```

## Supabase setup

- Create a Supabase project.
- Apply the migration in `supabase/migrations/001_initial_schema.sql`.
- Configure environment variables or use Streamlit secrets.
- Keep credentials out of version control.

## Security

- Do not commit real credentials.
- Use environment variables or Streamlit secrets.
- Never expose a service-role key in client-side code.
- Enable RLS for exposed tables in Supabase.

## Testing

```bash
pytest
```

## Notes

This V1 intentionally excludes live market APIs, SEC ingestion, AI research, and brokerage features.
