from setuptools import setup

setup(name='jockbot_mlb',
      version='0.6',
      description='Retrieve info from MLB API',
      url='http://github.com/jalgraves/jockbot_mlb',
      author='Jonny Graves',
      author_email='jal@jalgraves.com',
      license='MIT',
      packages=['jockbot_mlb'],
      zip_safe=False,
      install_requires=['aiohttp', 'python-dateutil'],
      include_package_data=True
      )
