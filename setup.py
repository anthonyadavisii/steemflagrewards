from distutils.core import setup

setup(
    name='steemflagrewards',
    version='0.0.3',
    packages=[''],
    url='https://github.com/Flugschwein/steemflagrewards',
    license='MIT',
    author='Flugschwein',
    author_email='flugschwein@gmx.at',
    description='A discord bot for steemflagrewards, a service incentivizing flagging on the steem blockchain',
    install_requires=['beem==0.19.48', 'git+https://github.com/Rapptz/discord.py@rewrite#egg=discord.py'],
    entry_points={
        'console_scripts' : ['steemflagrewards = steemflagrewards.sfrboty:main']
    }
)
