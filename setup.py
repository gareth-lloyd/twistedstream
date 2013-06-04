from setuptools import setup

DESCRIPTION = "A Twisted Library to consume the Twitter Streaming API"

LONG_DESCRIPTION = None
try:
    LONG_DESCRIPTION = open('README').read()
except:
    pass

VERSION = '0.12'
print VERSION

setup(name='twistedstream',
      version=VERSION,
      packages=['twistedstream'],
      author='Gareth Lloyd',
      author_email='glloyd@gmail.com',
      license='MIT',
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      platforms=['any']
)
