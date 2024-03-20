.PHONY: freeze requirements.txt

# Make sure to install uv
develop:
	uv venv
	source .venv/bin/activate && uv pip install -r requirements.txt

freeze:
	uv pip freeze | uv pip compile - -o requirements.txt

install: requirements.txt
	source .venv/bin/activate && uv pip install -r requirements.txt
