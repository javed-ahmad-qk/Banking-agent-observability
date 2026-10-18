.PHONY: install run test lint eval clean

install:
	python -m pip install -e '.[dev]'

run:
	banking-agent

test:
	pytest

lint:
	ruff check .

eval:
	banking-eval

clean:
	rm -f data/*.sqlite3 data/*.sqlite3-shm data/*.sqlite3-wal evaluation-report.json
