from setuptools import setup

classifiers = [
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Intended Audience :: Telecommunications Industry',
    'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
    'Natural Language :: English',
    'Programming Language :: Python :: 3.8'
]


setup(
    name='anon_chat_bot',
    version="0.0.1",
    url="https://github.com/Jacotsu/telegram_anon_chat_bot",
    author="jacotsu",
    license='GPLv3+',
    install_requires=[
        "dateparser",
        "configobj",
        "pytimeparyse",
        "captcha",
        "python_telegram_bot",
        "Telethon",
        "validate"
    ],
    python_requires='>=3.8',
    packages=['anon_chat_bot'],
    description="Create an anonymous chat lounge on telegram",
    classifiers=classifiers,
    entry_points={
        'console_scripts': [
            'anon_chat_bot=anon_chat_bot.main:main',
        ]
    }
)
