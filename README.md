# braintrust-load-test

To run it, first install [uv](https://github.com/astral-sh/uv), and then run

```bash
uv run generate_load.py --threads 1 --total-requests 1000
```

To run without `uv`, then do

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python generate_load.py --threads 1 --total-requests 1000
```

Make sure to set `BRAINTRUST_APP_URL`, etc. to point to your local env.
