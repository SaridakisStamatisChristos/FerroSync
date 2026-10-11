.PHONY: test static verify bench

static:
	PYTHONPATH=src python -m compileall -q src tests scripts

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

verify: static test
	python scripts/verify_manifest.py

bench:
	PYTHONPATH=src python scripts/bench.py --quick
