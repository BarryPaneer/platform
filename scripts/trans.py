#!/bin/bash
"""
Simple translation utility for handling .po files to .mo files, also including djangojs.js generation.
"""

import argparse
import logging
import os
import subprocess


PLAT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPILE_JS_CMD = [[
    "python", "manage.py", "lms", "--settings={}", "compilejsi18n"
], [
    "python", "manage.py", "cms", "--settings={}", "compilejsi18n"
]]
DJANGO_PO = "django.po"
DJANGO_JS_PO = "djangojs.po"
DJANGO_MO = "django.mo"
DJANGO_JS_MO = "djangojs.mo"
LANGUAGES = ["es_419", "fr", "pt_BR", "zh_CN", "eo", "it_IT", "de_DE", "tr_TR", "el", "ar"]  # "eo" is only used for test.

logging.basicConfig(level=logging.INFO)


def execute_cmd(cmd, shell=False):
    """Execute subprocess command(shell command).
    
    Args:
        cmd: string or a sequence of program arguments.
        shell: If using shell to  execute command.
    """
    try:
        logging.info("Executing \"{}\"".format(" ".join(cmd)))
        retcode = subprocess.call(cmd, shell=shell)
        if retcode < 0:
            logging.warning('Child process was terminated by signal: %s', -retcode)
        else:
            logging.info('Child process returned: %s', retcode)
    except OSError as e:
        logging.exception("Execution failed: ", e)


def compile_mo(lang):
    """Compiles po files to mo files.
    """
    logging.info('Start to handle {}'.format(lang))
    if os.path.exists(file_path(DJANGO_PO, lang)):
        cmd = ["msgfmt", "-o", file_path(DJANGO_MO, lang), file_path(DJANGO_PO, lang)]
        execute_cmd(cmd)
    else:
        logging.warning("django.po file for %s is not existed, skip..." % lang)

    if os.path.exists(file_path(DJANGO_JS_PO, lang)):
        cmd = ["msgfmt", "-o", file_path(DJANGO_JS_MO, lang), file_path(DJANGO_JS_PO, lang)]
        execute_cmd(cmd)
    else:
        logging.warning("djangojs.po file for %s is not existed, skip..." % lang)


def compile_js(settings):
    """Compiles po files to djangjs.js files.
    """
    logging.info('Handle djangojs.js generation...')
    for cmd in COMPILE_JS_CMD:
        cmd[3] = cmd[3].format(settings)
        execute_cmd(cmd)


def file_path(filename, lang="en"):
    """Finds specific file name's path according specific language.
    """
    return os.path.join(PLAT_PATH,
                        "conf/locale/{}/LC_MESSAGES/{}".format(lang, filename))


def main():
    parser = argparse.ArgumentParser(description="translation utility for Triboo")
    parser.add_argument('language', nargs='*', help="languages need to be translated")
    parser.add_argument('-a', '--all', action='store_true', help="handle all languages' translation")
    parser.add_argument('--settings', help="settings environment", default="devstack_docker")
    args = parser.parse_args()

    logging.info('Init work...')
    if args.all:
        for lang in LANGUAGES:
            compile_mo(lang)
        compile_js(args.settings)
    else:
        for lang in set(args.language):
            if not lang in LANGUAGES:
                logging.warning("invalid language code: %s, skip..." % lang)
                continue
            compile_mo(lang)
        if args.language:
            compile_js(args.settings)


if __name__ == "__main__":
    main()
