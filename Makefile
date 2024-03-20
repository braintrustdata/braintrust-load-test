.PHONY: freeze requirements.txt
freeze:
	uv pip freeze | uv pip compile - -o requirements.txt

install: requirements.txt
	uv pip install -r requirements.txt
