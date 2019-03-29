test:
	nosetests tests/test_mlb.py

dist:
	python37 setup.py sdist bdist_wheel

clean:
	rm -rf dist/ && rm -rf build/ && rm -rf jockbot_mlb.egg-info

pypi:
	python37 -m twine upload dist/*

publish: dist pypi clean