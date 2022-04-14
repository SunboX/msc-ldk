# ----------------------------------------------------------------------------------
#  Title      : Bootstrap libMscBoostPython
#  Project    : libMscBoostPython
# ----------------------------------------------------------------------------------
#  File       : bootstrap_msc_boost_python.py
#  Author     : Stefan Reichoer
#  Company    : MSC Technologies
#  Created    : 2016-06-27
# ----------------------------------------------------------------------------------
#  Description: Download libMscBoostPython when necessary
# ----------------------------------------------------------------------------------
#  Copyright (c) 2016 -- MSC Technologies
# ----------------------------------------------------------------------------------

import os
import shutil
import subprocess
import sys

try:
    MAIN_SCRIPT_DIR = os.path.dirname(os.path.realpath(sys.modules['__main__'].__file__))
except AttributeError:
    MAIN_SCRIPT_DIR = os.getcwd()

MSC_PUBLIC_GIT_SERVER = "ssh://gitolite@msc-git02.msc-ge.com:9418/"
MSC_GIT_SERVER = os.environ.get("MSC_GIT_SERVER", MSC_PUBLIC_GIT_SERVER)
MSC_GIT_SERVER = MSC_GIT_SERVER.rstrip("/")

def check_for_pip3():
    pip3_available = shutil.which("pip3")
    if not pip3_available:
        return ["sudo apt-get install python3-pip"]
    return []

class PipInstall(object):
    def __init__(self, module_name, pip_package_name):
        self.module_name = module_name
        self.pip_package_name = pip_package_name
    def check(self):
        try:
            exec("import %s" % self.module_name)
        except ImportError:
            return ["sudo pip3 install %s" % self.pip_package_name]
        return []

class WorkingDirectory(object):
    def __init__(self, directory):
        self.directory = directory
        self.old_dir = os.getcwd()
        os.chdir(directory)
    def __enter__(self):
        return None
    def __exit__(self, type_, value_, traceback_):
        if type_:
            print("Error during processing in '%s'" % self.directory, file=sys.stderr)
        os.chdir(self.old_dir)
        return False

def run_cmd(cmd, verbose=False):
    print("Executing '%s'" % cmd)
    if verbose:
        os.system(cmd)
    else:
        try:
            output = subprocess.check_output(cmd.split(" "), stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            print(e.output.decode("utf-8"))
            return False
    return True

def get_git_branch_name():
    return os.popen("git rev-parse --abbrev-ref HEAD").read().strip()

def get_git_tags():
    return os.popen("git tag").read().split()

def get_git_branches():
    remote_branches = os.popen("git branch -r").read().split("\n")
    remote_branches.sort(reverse=True)
    branches = []
    for branch in remote_branches:
        branch = branch.strip()
        if not branch or "->" in branch:
            continue
        branch_name = branch.partition("origin/")[2]
        branches.append(branch_name)
    return branches

def is_git_version_present(version):
    try:
        subprocess.check_call(["git", "cat-file", "-e", version], stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        return False
    return True

def is_head_at_git_version(version):
    pretty_versions = os.popen("git log --pretty=format:%d -1").read()
    if "tag: %s" % version in pretty_versions:
        return True
    return False

def get_valid_branch_name(branch):
    if branch is not None:
        msc_boost_python_branches = get_git_branches()
        if branch in msc_boost_python_branches:
            pass
        elif branch.startswith("feature"):
            branch = "develop"
        else:
            branch = "master"
    return branch

def git_clone_msc_boost_python(branch, version=None):
    cmd = "git clone %s/msc/0000/libMscBoostPython libMscBoostPython.git" % MSC_GIT_SERVER
    if run_cmd(cmd, verbose=True):
        with WorkingDirectory("libMscBoostPython.git"):
            branch = get_valid_branch_name(branch)
            current_branch_name = get_git_branch_name()
            if branch != current_branch_name:
                checkout_cmd = "git checkout -b %s" % branch
                run_cmd(checkout_cmd)
                upstream_set_cmd = "git branch --set-upstream-to=origin/%s %s" % (branch, branch)
                run_cmd(upstream_set_cmd)
                git_checkout_msc_boost_python(None, version)
            return True
    return False

def git_checkout_msc_boost_python(branch, version):
    branch = get_valid_branch_name(branch)
    if branch is not None:
        checkout_cmd = "git checkout %s" % branch
        run_cmd(checkout_cmd)
    if not is_git_version_present(version):
        run_cmd("git pull")
    run_cmd("git checkout %s" % version)

def check_python_requirements():
    command_list = []
    command_list.extend(check_for_pip3())

    git_python = PipInstall("git", "gitpython")
    command_list.extend(git_python.check())
    if command_list:
        print("Dependencies for libMscBoostPython are not met")
        print("Please issue the following commands:")
        print("\n".join(command_list))
        return False
    return True

def install_msc_boost_python(version):
    with WorkingDirectory(MAIN_SCRIPT_DIR):
        branch_name = get_git_branch_name()
        if not os.path.isdir("libMscBoostPython.git"):
            print("Cloning libMscBoostPython (version: %s)" % version)
            git_clone_msc_boost_python(branch_name, version)
            if not os.path.islink("MscBoost"):
                os.symlink("libMscBoostPython.git/src/MscBoost", "MscBoost")
        else:
            with WorkingDirectory("libMscBoostPython.git"):
                if is_git_version_present(version):
                    if not is_head_at_git_version(version):
                        print("Switching libMscBoostPython to '%s'" % version)
                        git_checkout_msc_boost_python(branch_name, version)
                else:
                    print("Updating libMscBoostPython to '%s'" % version)
                    git_checkout_msc_boost_python(branch_name, version)

def bootstrap_msc_boost_python(version):
    if check_python_requirements():
        install_msc_boost_python(version)
        return
    sys.exit(1)
