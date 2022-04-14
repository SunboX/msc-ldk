#!/usr/bin/env python3
# ----------------------------------------------------------------------------------
#  Title      : Yocto Setup for MSC-LDK
#  Project    : MSC-LDK
# ----------------------------------------------------------------------------------
#  File       : setup.py
#  Author     : Stefan Reichoer
#  Company    : MSC Technologies
#  Created    : 2016-07-01
# ----------------------------------------------------------------------------------
#  Description: Yocto Setup for MSC-LDK
# ----------------------------------------------------------------------------------
#  Copyright (c) 2016 -- MSC Technologies
# ----------------------------------------------------------------------------------

import sys

print("""
MSC-LDK has been moved. This repository will no longer be updated.
Please fetch MSC-LDK from the new repository:

  git clone ssh://gitolite@msc-git02.msc-ge.com:9418/msc_ol99/msc-ldk

You can move the directories downloads/ and sstate-cache/ from this directory to the new cloned MSC-LDK to improve build speed.
""")

import bootstrap_msc_boost_python
bootstrap_msc_boost_python.bootstrap_msc_boost_python("v0.4.2")

import configparser
import datetime
import glob
import os
import subprocess

import MscBoost.Logging as Logging
import MscBoost.Git as Git
import MscBoost.Util as Util
import MscBoost.MscProject as MscProject

from MscBoost.Application import Application
from MscBoost.FilePath import FilePath
from MscBoost.FindBestMatch import FindBestMatch

MSC_GIT_SERVER = Git.get_git_server()
MSC_GIT_SERVER_CACHE = Git.get_git_server_cache()

LOG = Logging.Log()

GIT_LOG_PRETTY_ONE_LINE_FORMAT = '--pretty=format:%C(auto)%H - %an, %ar : %Cgreen%s%C(auto)%d'

def cmd_exists(cmd):
    return subprocess.getstatusoutput("which %s" % cmd)[0] == 0

def check_tools():
    LOG.info("Checking tools for building images")
    req_tools = ["make", "git"]
    req_tools_ce85 = ["lzop"]
    for tool in req_tools + req_tools_ce85:
        if not cmd_exists(tool):
            LOG.error("'%s' not available" % tool)
    LOG.info("Checking tools for building optional Yocto documentation")
    doc_tools = ["xsltproc", "fop"]
    for tool in doc_tools:
        if not cmd_exists(tool):
            LOG.error("'%s' is necessary for optional 'make yocto-doc'" % tool)
    LOG.notice("Checked Tools")

def check_git_access():
    LOG.info("Checking access to git server")
    if Git.check_git_access():
        LOG.notice("o.k.")
    else:
        LOG.error("failed")

def ensure_ssh_mirror_is_known():
    if not cmd_exists("ssh-keygen"):
        LOG.error("ssh-keygen is not installed (it is e.g. in package openssh-client on Ubuntu)")
        return False
    if subprocess.getstatusoutput("ssh-keygen -F ftp4.ebv.com")[0] == 0:
        return True
    ssh_user_dir = os.path.expanduser("~/.ssh")
    if not os.path.exists(ssh_user_dir):
        os.mkdir(ssh_user_dir, 0o700)
    known_hosts_file = os.path.expanduser("~/.ssh/known_hosts")
    if not os.path.exists(known_hosts_file):
        fd = os.open(known_hosts_file, os.O_CREAT | os.O_WRONLY, 0o644)
        os.close(fd)
    f = open(known_hosts_file, "a")
    f.write("ftp4.ebv.com,172.22.131.201 ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBBa7Kg+jEoE2N5yih71OBG1o+Uci85KUfyORwqIdRcvvJIZRQ6jL1v3EaobnE6cAfhn1d7TvS3T+LUx09dgw7U0=  \n")
    f.close()
    LOG.info("Added host 'ftp4.ebv.com' to %s" % known_hosts_file)
    return True

class MscLdkLayerDirectory(object):
    def __init__(self, msc_ldk_dir, layer_directory):
        self.full_layer_directory = layer_directory
        sources_prefix = os.path.join(msc_ldk_dir, "sources/")
        if layer_directory.startswith(sources_prefix):
            self.layer_directory = layer_directory[len(sources_prefix):]
        elif layer_directory == msc_ldk_dir:
            self.layer_directory = "msc-ldk"
        else:
            self.layer_directory = layer_directory
        self.git_repo = GitRepository(layer_directory)
    def __repr__(self):
        return "<Layer %s>" % self.layer_directory
    def get_head_sha1(self):
        return self.git_repo.get_head_sha1()
    def is_sha1_present(self, sha1):
        try:
            subprocess.check_call(["git", "cat-file", "-e", sha1], cwd=self.full_layer_directory, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            return False
        return True
    def is_branch_present(self, branch):
        branch_names = self.git_repo.get_branch_names(local=True, remote=True)
        return branch in branch_names
    def is_msc_ldk(self):
        return self.layer_directory == "msc-ldk"

class MscLdkSnapshot(object):
    def __init__(self, msc_ldk_dir, id_string, bsp_build_root, bsp_mapping):
        self.msc_ldk_dir = msc_ldk_dir
        self.id_string = id_string
        self.bsp_build_root = bsp_build_root
        self.bsp_mapping = bsp_mapping

    def parse_bblayers(self, file_name):
        WAIT_FOR_BBLAYERS, BUILD_BBLAYERS, DONE = range(3)
        state = WAIT_FOR_BBLAYERS
        for line in open(file_name).readlines():
            line = line.rstrip()
            if state == WAIT_FOR_BBLAYERS and line.startswith("BBLAYERS "):
                state = BUILD_BBLAYERS
                bb_layers = line.partition('"')[2].rstrip("\\")
            elif state == BUILD_BBLAYERS:
                # print line
                if '"' in line:
                    state = DONE
                    bb_layers += line.partition('"')[0]
                else:
                    bb_layers += line.rstrip("\\")
        layers = bb_layers.split()
        return layers

    def get_ldk_layers(self, include_msc_ldk=False):
        self.layer_repo_layers = {}
        repo_list = []
        bblayers_conf = os.path.join(self.bsp_build_root, "conf", "bblayers.conf")
        for layer in self.parse_bblayers(bblayers_conf):
            dir_candidate = layer
            layer_name = layer[len(os.path.join(self.msc_ldk_dir, "sources/")):]
            while dir_candidate:
                if os.path.exists(os.path.join(dir_candidate, ".git")):
                    if dir_candidate not in repo_list:
                        repo_list.append(dir_candidate)
                        self.layer_repo_layers[dir_candidate] = [layer_name]
                    else:
                        self.layer_repo_layers[dir_candidate].append(layer_name)
                    dir_candidate = None
                else:
                    dir_candidate = os.path.dirname(dir_candidate)
        if include_msc_ldk:
            repo_list.insert(0, self.msc_ldk_dir)
        return repo_list

    def get_layer_directories(self, include_msc_ldk=True):
        return [MscLdkLayerDirectory(self.msc_ldk_dir, layer_directory) for layer_directory in self.get_ldk_layers(include_msc_ldk)]

    def show_layer_info(self):
        for layer_directory in self.get_layer_directories():
            layers = self.layer_repo_layers.get(layer_directory)
            if not layers:
                layer_info_string = ""
            elif len(layers) == 1:
                layer_info_string = ", Layer: %s" % layers[0]
            else:
                layer_info_string = ", Layers: %s" % ", ".join(layers)
            header = "%s, %s%s" % (layer_directory.full_layer_directory, layer_directory.git_repo.get_checkout_info_string(), layer_info_string)
            print(Logging.colorize(Logging.COLOR.pink, header))
            print(Util.indent_text(layer_directory.git_repo.git.log(GIT_LOG_PRETTY_ONE_LINE_FORMAT, '-5')))

    def read_version_layer(self, file_name):
        snapshot = configparser.ConfigParser()
        snapshot["general"] = {}
        snapshot["general"]["comment"] = "Converted version_layer on %s" % Util.get_timestamp_string()
        snapshot["general"]["version_layer"] = "True"
        # pass1: read MSC-LDK version and SETUP parameters
        for line in open(file_name).readlines():
            line = line.strip()
            if " built on " in line:
                # e.g.: MSC-LDK initial_separated-103-gaeccd82-dirty built on Sat Sep 17 00:42:41 CEST 2016 by buildserver@destsm3ux05bs01.emea.avnet.com
                version, dummy, time_and_machine = line.partition(" built on ")
                version = version.split(" ")[1]
                timestamp_str, dummy, machine = time_and_machine.partition(" by ")
                try:
                    timestamp = datetime.datetime.strptime(timestamp_str, "%a %b %d %H:%M:%S %Z %Y")
                    snapshot["general"]["timestamp"] = Util.get_timestamp_string(timestamp)
                except ValueError:
                    pass
                snapshot["general"]["machine"] = machine
                snapshot["msc-ldk"] = {}
                if version.endswith("-dirty"):
                    snapshot["msc-ldk"]["dirty"] = "True"
                    version = version[:-6]
                snapshot["msc-ldk"]["version"] = version
                continue
            elif "--bsp" in line:
                # e.g.: --bsp=0000 --variant=32 --layers-hwtests --re-create-conf
                options = line.split(" ")
                bsp = "???"
                variant = ""
                layers = []
                for option in options:
                    name, dummy, value = option.partition("=")
                    name = name.strip()
                    value = value.strip()
                    if name == "--bsp":
                        bsp = self.bsp_mapping.get(value, value)
                    elif name == "--variant":
                        variant = value
                    elif name.startswith("--layers-"):
                        layers.append(name[len("--layers-"):])
                layers.sort()
                id_elems = [bsp]
                if variant:
                    id_elems.append(variant)
                if layers:
                    id_elems.extend(layers)
                id_string = "-".join(id_elems)
                snapshot["general"]["id"] = id_string
        # pass2: read layer information
        for line in open(file_name).readlines():
            line = line.strip()
            if line.startswith("LAYER "):
                line = line[6:]
                # e.g.: MSC-LDK meta-openembedded=LC984_20160504_V1_0_0
                layer, version = line.split("=")
                if layer == "msc-ldk-bsp-recipes":
                    layer = "%s/%s" % (bsp, layer)
                layer += ".git"
                snapshot[layer] = {}
                if version.endswith("-dirty"):
                    snapshot[layer]["dirty"] = "True"
                    version = version[:-6]
                snapshot[layer]["version"] = version
        self.snapshot_origin = ("--version-file", os.path.abspath(file_name))
        self.snapshot = snapshot

    def extract_bsp_info(self, known_layers):
        snapshot_id = self.snapshot.get("general", "id")
        id_elems = snapshot_id.split("-")
        bsp = id_elems[0]
        variant = ""
        layers = []
        for elem in id_elems[1:]:
            if elem in known_layers:
                layers.append(elem)
            else:
                variant = elem
        return bsp, variant, layers

    def use_snapshot_file(self, dry_run):
        self.use_snapshot_config(self.snapshot, self.snapshot_origin, dry_run)

    def switch_msc_ldk_git_to_snapshot_version(self, snapshot, dry_run):
        version = snapshot.get("msc-ldk", "version", fallback=None)
        if version is None:
            version = snapshot.get("msc-ldk", "sha1", fallback=None)
        msc_ldk_git = GitRepository(self.msc_ldk_dir)
        head_sha1 = msc_ldk_git.get_head_sha1()
        desired_sha1 = msc_ldk_git.get_sha1_for_version(version)
        if head_sha1 == desired_sha1:
            # Already at desired version
            return True
        if msc_ldk_git.is_dirty():
            LOG.error("Cannot switch %s from %s to %s (working tree is dirty)" % (msc_ldk_git, head_sha1, desired_sha1))
            LOG.error("Please stash or commit your changes")
            return False
        switch_info_string = "Switching MSC-LDK from %s to %s" % (head_sha1, desired_sha1)
        if dry_run:
            switch_info_string += " (dry-run)"
        print(Logging.colorize(Logging.COLOR.pink, switch_info_string))
        if not dry_run:
            if msc_ldk_git.is_in_detached_head_state():
                msc_ldk_git.git.checkout("-")
                LOG.out(2, "%s: git checkout -" % msc_ldk_git)
            msc_ldk_git.git.checkout(desired_sha1)
            head_sha1 = msc_ldk_git.get_head_sha1()
            if head_sha1 == desired_sha1:
                return "switched"
            else:
                LOG.error("  MSC-LDK switching failed")
                return False
        else:
            return False

    def use_snapshot_config(self, snapshot, snapshot_origin, dry_run):
        snapshot_timestamp = snapshot.get("general", "timestamp")
        snapshot_id = snapshot.get("general", "id")
        import_from_version_layer = snapshot.has_option("general", "version_layer")
        LOG.info("Analyzing MSC-LDK layer snapshot from: '%s' (created at %s)" % (snapshot_origin[1], snapshot_timestamp))
        switched_msc_ldk = self.switch_msc_ldk_git_to_snapshot_version(snapshot, dry_run)
        if switched_msc_ldk == "switched":
            cmd = os.path.join(self.msc_ldk_dir, "scripts", "setup.py")
            # Add --version-file
            cmd += " %s %s" % snapshot_origin
            run_setup_string = "Starting setup.py: '%s'" % cmd
            print(Logging.colorize(Logging.COLOR.pink, run_setup_string))
            os.system(cmd)
            return False
        elif not switched_msc_ldk:
            # Aborted
            if not dry_run:
                return False

        warn_count1 = Logging.get_log_call_count("WARNING")
        if self.id_string != snapshot_id:
            if import_from_version_layer:
                # snapshot_id does not consider the default variant for the BSP -> skip the warning below
                pass
            else:
                LOG.warn("Current MSC-LDK Id: %s does not match snapshot Id: %s" % (self.id_string, snapshot_id))
        snapshot_layers = snapshot.sections()
        snapshot_layers.remove("general")
        snapshot_info = []
        for layer_directory in self.get_layer_directories(include_msc_ldk=True):
            layer_name = layer_directory.layer_directory
            if layer_name in snapshot_layers:
                snapshot_layers.remove(layer_name)
                snapshot_branch = snapshot.get(layer_name, "branch", fallback=None)
                snapshot_version = snapshot.get(layer_name, "version", fallback=None)
                snapshot_version_dirty = snapshot.get(layer_name, "dirty", fallback=False)
                if snapshot_version is not None:
                    version_str = "Version"
                    version_or_sha1 = snapshot_version
                else:
                    version_or_sha1 = snapshot.get(layer_name, "sha1", fallback=None)
                    version_str = "SHA1"
                if snapshot_version_dirty:
                    LOG.warning("  Layer '%s' was dirty: %s" % (layer_name, version_or_sha1))
                    warn_count1 += 1 # not a critical warning...
                if snapshot_branch is not None:
                    if not layer_directory.is_branch_present(snapshot_branch):
                        LOG.warn("Layer %s: branch '%s' is not present" % (layer_name, snapshot_branch))
                        snapshot_branch = None
                if not layer_directory.is_sha1_present(version_or_sha1):
                    LOG.warn("Layer %s: %s '%s' is not present" % (layer_name, version_str, version_or_sha1))
                    version_or_sha1 = None
                if layer_directory.git_repo.is_dirty():
                    LOG.warn("Layer %s is dirty - please commit or stash your changes first" % layer_directory.full_layer_directory)
                    layer_directory.git_repo.show_diff()
                if not layer_directory.is_msc_ldk():
                    snapshot_info.append((layer_directory, snapshot_branch, version_or_sha1))
            else:
                LOG.warn("Uncovered layer '%s' - not found in snapshot file" % layer_name)
        for unprocessed_snapshot_layer in snapshot_layers:
            LOG.warn("Additional layer in snapshot file '%s' - not used in MSC-LDK project" % unprocessed_snapshot_layer)
        warn_count2 = Logging.get_log_call_count("WARNING")
        if warn_count2 == warn_count1:
            switch_info_string = "Switching Layer repositories to snapshot position"
            if dry_run:
                switch_info_string += " (dry-run)"
            num_switched_layers = 0
            for layer_directory, branch, version in snapshot_info:
                git_repo = GitRepository(layer_directory.full_layer_directory)
                cur_branch = git_repo.get_active_branch_name()
                sha1 = git_repo.get_sha1_for_version(version)
                if cur_branch != branch and branch is not None:
                    LOG.notice("%s: Switching branch from %s -> %s" % (layer_directory, cur_branch, branch))
                    if not dry_run:
                        git_repo.git.checkout(branch)
                cur_sha1 = git_repo.get_head_sha1()
                if cur_sha1 != sha1:
                    if num_switched_layers == 0:
                        print(Logging.colorize(Logging.COLOR.pink, switch_info_string))
                    num_switched_layers += 1
                    LOG.notice("%s: Switching checked out SHA1 from %s -> %s" % (layer_directory, cur_sha1, sha1))
                    if not dry_run:
                        if git_repo.is_in_detached_head_state():
                            git_repo.git.checkout("-")
                            LOG.out(2, "%s: git checkout -" % git_repo)
                        git_repo.git.checkout(sha1)
            if num_switched_layers == 0:
                print(Logging.colorize(Logging.COLOR.pink, "All Layer repositories are already at their requested versions"))
        else:
            LOG.error("Aborting Snapshot Activation")
            return False
        return True


class YoctoLayer(object):
    def __init__(self, layer_name, file_name):
        self.name = layer_name
        self.file_name = file_name
    def __repr__(self):
        return "<YoctoLayer %s>" % self.name
    def description(self):
        for line in open(self.file_name).readlines():
            # Extract layer description from .csv, e.g.: '# Description: Layer description, blah, blah...'
            layer_description = line.partition("# Description:")[2].strip()
            if layer_description:
                return layer_description
        return self.name

class GitRepository(Git.GitRepository):
    def is_on_develop_branch(self):
        active_branch_name = self.get_active_branch_name()
        if active_branch_name is not None and (active_branch_name == "develop" or active_branch_name.startswith("feature/")):
            return True
        return False
    def is_on_master_branch(self):
        return self.get_active_branch_name() == "master"
    def get_repo_tag(self):
        if self.is_on_develop_branch() or self.is_on_master_branch():
            return ""
        tag_string = subprocess.getoutput("git describe --tags")
        return tag_string
    def show_diff(self):
        unstaged_diff = self.git.diff()
        staged_diff = self.git.diff("--staged")
        if unstaged_diff:
            LOG.out(1, unstaged_diff)
        if staged_diff:
            LOG.out(1, "Staged changes:")
            LOG.out(1, staged_diff)

class SetupMscLdkApplication(Application):
    def __init__(self):
        super().__init__("setup.py", "Setup script to initialize MSC-LDK.")
        self.arg_parser.add_argument("--bsp", help="BSP id.")
        self.arg_parser.add_argument("--variant", default="", help="Variant to build (e.g. 32 or 64).")

        self.arg_parser.add_argument("--local-conf-append", help="The content of the given file is appended to 'local.conf'.")

        self.arg_parser.add_argument("--checkout-layers", action="store_true", help="Run git checkout on the layers to match the branch that is used in MSC-LDK.")
        self.arg_parser.add_argument("--re-create-conf", action="store_true", help="Force re-creation of 'local.conf', 'bblayers.conf'.")

        self.arg_parser.add_argument("--version-file", help="Setup MSC-LDK layers to match VERSION_FILE.")
        self.arg_parser.add_argument("--show-layer-info", action="store_true", help="Show MSC-LDK layer info.")

        self.arg_parser.add_argument("--dry-run", action="store_true", help="Don't perform some actions (Available for --version-file).")

        self.show_recreate_conf_warning = True
        self.inform_about_checkout_layers = False
        self._determine_msc_ldk_root()
        self.msc_ldk_sources = os.path.join(self.msc_ldk_root, "sources")
        self.msc_ldk_scripts = os.path.join(self.msc_ldk_root, "scripts")

        self.parse_bsp_mapping()
        self.detect_supported_layers()

    def _determine_msc_ldk_root(self):
        self.msc_ldk_root = os.path.abspath(os.getcwd())
        keep_searching_for_msc_ldk_root = True
        while keep_searching_for_msc_ldk_root:
            if os.path.exists(os.path.join(self.msc_ldk_root, ".git")):
                keep_searching_for_msc_ldk_root = False
            else:
                self.msc_ldk_root = os.path.dirname(self.msc_ldk_root)
                if self.msc_ldk_root == "/":
                    keep_searching_for_msc_ldk_root = False
        self.bsp_build_dir_name = None
        self.bsp_build_root = None
        self.default_settings_file = os.path.join(self.msc_ldk_root, "MSC-LDK.default-config")

    def _get_usage_examples(self):
        return """\
  ./setup.py: will check that all necessary tools are installed
  ./setup.py --bsp=C984: will download and prepare the BSP for the project/board C984.
  ./setup.py --bsp=C984 --variant=32: will download and prepare the BSP for the project/board C984 in the 32bit variant.
  ./setup.py --bsp=C984 --variant=64 --layers-lxqt: will download and prepare the BSP for the project/board C984 in the 64bit variant. The required layers for LXQt are enabled.
  ./setup.py --version-file version_file --dry-run: Shows what will be done to setup a BSP build with the layer versions specified in version_file.
  ./setup.py --version-file version_file: Setup a BSP build with the layer versions specified in version_file.
        """

    def _print_version(self):
        """Prints the application version. As this script is not part of a cmake environment, we have to provide our own implementation."""
        # This is not a full MscProject (missing COPYING etc.),
        # but is sufficient for getting the version

        proj = MscProject.MscProject(self.msc_ldk_root)
        LOG.out(0, "Version: {}".format(str(proj.version)))

    def _print_copyright(self):
        """Prints the copyright. As this script is not part of a cmake environment, we have to provide our own implementation."""
        with open(os.path.join(self.msc_ldk_root, "COPYING_linked")) as f:
            LOG.out(0, f.read())

    def did_errors_or_warnings_happen(self):
        return Logging.get_log_call_count("ERROR") + Logging.get_log_call_count("WARNING") > 0

    def in_msc_network(self):
        return MSC_GIT_SERVER in ["gitosis@msc-aac-debian01.msc-ge.mscnet:/"]

    def parse_bsp_mapping(self):
        bsp_mapping_file_name = "bsp-mapping.csv"
        self.bsp_mapping = {}
        with Util.WorkingDirectory(self.msc_ldk_scripts):
            if os.path.exists(bsp_mapping_file_name):
                for line in open(bsp_mapping_file_name).readlines():
                    bsp_nr, *bsp_aliases = line.strip().split(",")
                    for alias in bsp_aliases:
                        self.bsp_mapping[alias] = bsp_nr

    def local_conf_name(self, variant):
        bsp_conf = os.path.join(self.bsp_layer, "conf")
        if variant:
            variant_file_name_part = "-"+variant
        else:
            variant_file_name_part = ""
        local_conf = os.path.join(bsp_conf, "local"+variant_file_name_part+".conf")
        return local_conf

    def determine_variant(self, variant):
        local_conf = self.local_conf_name(variant)
        if not os.path.exists(local_conf):
            bsp_conf = os.path.join(self.bsp_layer, "conf")
            possible_variants = glob.glob(os.path.join(bsp_conf, "local-*.conf"))
            possible_variants = [v.rpartition("local-")[2].partition(".conf")[0] for v in possible_variants]
            LOG.error("Variant '%s' not supported, possible variants: %s" % (variant, ", ".join(possible_variants)))
            self._exit(2)
        if os.path.islink(local_conf):
            # Determine variant name from real path of the used local.conf file
            real_local_conf = os.path.basename(os.path.realpath(local_conf))
            variant = real_local_conf.rpartition("local-")[2].partition(".conf")[0]
        return variant

    def detect_supported_layers(self):
        self.layers = []
        with Util.WorkingDirectory(self.msc_ldk_scripts):
            for layer_file_name in sorted(glob.glob("layers-*.csv")):
                layer_name = layer_file_name.partition("layers-")[2].partition(".")[0]
                if layer_name == "core":
                    continue
                layer = YoctoLayer(layer_name, os.path.join(self.msc_ldk_scripts, layer_file_name))
                self.layers.append(layer)
                self.arg_parser.add_argument("--layers-%s" % layer_name,
                                             help="Enable %s layers." % layer.description(),
                                             action="store_true")

    def find_best_git_ref(self, repo_path, requested_git_ref, force_branch=False):
        g = GitRepository(repo_path)
        repo_branch_names = g.get_branch_names(local=True, remote=True)
        repo_tag_names = g.get_tag_names()
        if self.git_repo_msc_ldk.is_on_develop_branch() and not force_branch:
            requested_git_ref = ""
        if requested_git_ref == "":
            if self.msc_ldk_active_branch_name is None:
                git_ref = self.msc_ldk_active_tag_name
            elif self.msc_ldk_active_branch_name not in ("develop", "master") and self.msc_ldk_active_branch_name in repo_branch_names:
                git_ref = self.msc_ldk_active_branch_name
            elif self.git_repo_msc_ldk.is_on_develop_branch() and self.msc_ldk_based_on_yocto_branch+"-msc-develop" in repo_branch_names:
                git_ref = self.msc_ldk_based_on_yocto_branch+"-msc-develop"
            elif self.msc_ldk_based_on_yocto_branch+"-msc" in repo_branch_names:
                git_ref = self.msc_ldk_based_on_yocto_branch+"-msc"
            elif self.msc_ldk_based_on_yocto_branch in repo_branch_names:
                git_ref = self.msc_ldk_based_on_yocto_branch
            elif self.git_repo_msc_ldk.is_on_develop_branch():
                git_ref = "develop"
                if git_ref not in repo_branch_names:
                    LOG.out(1, "  Using fallback branch 'master' for repo: %s (branch 'develop' does not exist)" % repo_path)
                    git_ref = "master"
            else:
                git_ref = "master"
        else:
            git_ref = requested_git_ref
        return git_ref

    def install_repo(self, relative_repo, install_to, branch="", force_branch=False):
        run_checkout = False
        prev_checkout_info = None
        if os.path.isdir(install_to):
            g = GitRepository(install_to)
            LOG.notice("Repository '%s' is already installed (%s)" % (relative_repo, g.get_checkout_info_string()))
            prev_checkout_info = g.get_checkout_info_string()
            if self.args.checkout_layers:
                run_checkout = True
        else:
            repo = MSC_GIT_SERVER + relative_repo
            LOG.notice("Installing repository '%s'" % repo)
            layer_base_dir = os.path.dirname(install_to)
            if not os.path.isdir(layer_base_dir):
                os.makedirs(layer_base_dir)
            Git.clone(repo, install_to)
            g = GitRepository(install_to)
            run_checkout = True

        repo_name = os.path.basename(relative_repo)
        LOG.out(2, "  Branches in repo %s: %s" % (repo_name, g.get_branch_names(remote=True)))
        LOG.out(2, "  TAGS in repo %s: %s" % (repo_name, g.get_tag_names()))
        git_ref = self.find_best_git_ref(install_to, branch, force_branch)
        if run_checkout:
            g.git.checkout(git_ref)
            if prev_checkout_info is not None:
                cur_checkout_info = g.get_checkout_info_string()
                if prev_checkout_info != cur_checkout_info:
                    LOG.notice("Repository '%s': Switched to <%s>" % (relative_repo, cur_checkout_info))
        if g.get_active_branch_name() != git_ref and g.get_repo_tag() != git_ref:
            LOG.error("Repository '%s' is not on the requested branch '%s' (it is at '%s')" % (install_to, git_ref, g.get_checkout_info_string()))
            self.inform_about_checkout_layers = True

    def install_all_layers(self):
        layer_files = [os.path.join(self.msc_ldk_scripts, "layers-core.csv")]
        layer_files.append(os.path.join(self.bsp_layer, "layers-bsp.csv"))
        for layer in self.active_layers:
            layer_files.append(os.path.join(self.msc_ldk_scripts, "layers-%s.csv" % layer.name))

        # BSP layer itself is not provided by layer_file
        self.msc_ldk_layers_for_bsp = [os.path.join(self.bsp_layer, "meta")]
        installed_repos = []
        for layer_file in layer_files:
            if os.path.exists(layer_file):
                LOG.out(1, "Processing: %s" % layer_file)
                for line in open(layer_file).readlines():
                    line = line.strip()
                    if line.startswith("#"):
                        continue # Support '#' comments
                    if "Relative GIT Repository" in line:
                        continue # Old .csv files start with a header line -> skip this line
                    try:
                        repo, subdir, branch = line.split(",")
                    except:
                        LOG.error("Malformed line in '%s': '%s'" % (layer_file, line))
                        LOG.error("  Expected repo,subdir,branch (three values, separated by two ',')")
                        continue
                    local_repo_dir = os.path.join(self.msc_ldk_sources, os.path.basename(repo)+".git")
                    if repo not in installed_repos:
                        self.install_repo(repo, local_repo_dir, branch)
                        installed_repos.append(repo)
                    layer_dir = os.path.join(local_repo_dir, subdir)
                    layer_entry = os.path.join(self.msc_ldk_root, layer_dir).rstrip("/")
                    if layer_entry not in self.msc_ldk_layers_for_bsp:
                        self.msc_ldk_layers_for_bsp.append(layer_entry)

    def create_bsp_info_files(self, bsp, variant):
        # Create .setup_cmdline.txt, .bsp.txt, .variant.txt
        setup_cmdline_txt_file = open(os.path.join(self.bsp_build_root, ".setup_cmdline.txt"), "w")
        cmd_line_param = " ".join(self.app_startup_information[2][1:])
        print(cmd_line_param, file=setup_cmdline_txt_file, end="")
        setup_cmdline_txt_file.close()

        bsp_txt_file = open(os.path.join(self.bsp_build_root, ".bsp.txt"), "w")
        print(bsp, file=bsp_txt_file, end="")
        bsp_txt_file.close()

        variant_txt_file = open(os.path.join(self.bsp_build_root, ".variant.txt"), "w")
        if variant:
            variant_file_content = "-%s" % variant
        else:
            variant_file_content = variant
        print(variant_file_content, file=variant_txt_file, end="")
        variant_txt_file.close()

    def update_bsp_conf(self, variant):
        local_conf = self.local_conf_name(variant)
        bsp_build_root_conf = os.path.join(self.bsp_build_root, "conf")
        if not os.path.isdir(bsp_build_root_conf):
            os.makedirs(bsp_build_root_conf)

        local_conf_file_name = os.path.join(bsp_build_root_conf, "local.conf")
        bblayers_conf_file_name = os.path.join(bsp_build_root_conf, "bblayers.conf")
        local_conf_file_bak = Util.make_timestamped_backup_file(local_conf_file_name, keep_old=False, bak_extension=".bak")
        bblayers_conf_file_bak = Util.make_timestamped_backup_file(bblayers_conf_file_name, keep_old=False, bak_extension=".bak")

        oe_init_build_env_cmd = 'bash -c "export TEMPLATECONF=\"{MSC_LDK_TEMPLATE_ROOT}\"; source \"{MSC_LDK_YOCTO_ROOT}/oe-init-build-env\" \"{BSP_BUILD_ROOT}\""'.format(
            MSC_LDK_TEMPLATE_ROOT=os.path.join(self.msc_ldk_root, "template"),
            MSC_LDK_YOCTO_ROOT=os.path.join(self.msc_ldk_sources, "yocto.git"),
            BSP_BUILD_ROOT=self.bsp_build_root)
        st, output = subprocess.getstatusoutput(oe_init_build_env_cmd)
        if "Error" in output:
            LOG.error("oe-init-build-env: '%s' -> '%s'" % (oe_init_build_env_cmd, output))

        msc_ldk_yocto_dl_dir = os.getenv("MSC_LDK_YOCTO_DL_DIR", os.path.join(self.msc_ldk_root, "downloads"))
        msc_ldk_yocto_sstate_dir = os.getenv("MSC_LDK_YOCTO_SSTATE_DIR", os.path.join(self.msc_ldk_root, "sstate-cache"))
        local_conf_file = open(local_conf_file_name, "a")
        local_conf_txt = """
# This has been added by setup.py

DL_DIR ?= "{MSC_LDK_YOCTO_DL_DIR}"
SSTATE_DIR ?= "{MSC_LDK_YOCTO_SSTATE_DIR}"
""".format(MSC_LDK_YOCTO_DL_DIR=msc_ldk_yocto_dl_dir, MSC_LDK_YOCTO_SSTATE_DIR=msc_ldk_yocto_sstate_dir)
        print(local_conf_txt, file=local_conf_file)
        local_conf_txt = r"""
# Setup permanent packet mirror
MIRRORS_append = "\
    https?$://.*/.* sftp://msc-ldk-mirror@ftp4.ebv.com/downloads/ \n \
    ftp://.*/.* sftp://msc-ldk-mirror@ftp4.ebv.com/downloads/ \n \
"

# This creates the directory buildhistory/ with various statistics and information about
# the generated image and used packages.
INHERIT += "buildhistory"
BUILDHISTORY_COMMIT = "0"
BUILDHISTORY_FEATURES = "image"

# disable this to generate .iso images
NOISO = "1"

# the default 1 second is too little as an attached display might be still reconfiguring
# so the bootprompt is displayed after the second has elapsed
SYSLINUX_TIMEOUT = "50"

PREFERRED_PROVIDER_jpeg = "libjpeg-turbo"
PREFERRED_PROVIDER_jpeg-native = "libjpeg-turbo-native"
""".format(MSC_GIT_SERVER_PUBLIC_HOST="msc-git02.msc-ge.com", MSC_GIT_SERVER_PUBLIC_PORT="9418")
        print(local_conf_txt, file=local_conf_file)
        print(open(local_conf).read(), file=local_conf_file)
        for layer in self.active_layers:
            for extra_conf in [os.path.join(self.msc_ldk_scripts, "local-%s.conf" % layer.name),
                               os.path.join(os.path.join(self.bsp_layer, "conf", "local-"+layer.name+".conf"))]:
                if os.path.exists(extra_conf):
                    print(open(extra_conf).read(), file=local_conf_file)
        user_config_anchor = "# User configuration should be placed below this line"
        print("\n%s" % user_config_anchor, file=local_conf_file)
        # Add content specified using --local-conf-append
        local_conf_append = self.args.local_conf_append
        if local_conf_append and os.path.exists(local_conf_append):
            print("\n# Configuration taken from '%s':" % os.path.abspath(local_conf_append), file=local_conf_file)
            print(open(local_conf_append).read(), file=local_conf_file)
        if self.args.re_create_conf and not local_conf_append:
            # When local.conf is re-generated: Keep lines below the user_config_anchor
            if local_conf_file_bak:
                add_user_lines = False
                for line in open(local_conf_file_bak):
                    if add_user_lines:
                        print(line, file=local_conf_file, end="")
                    elif line.strip("\n") == user_config_anchor:
                        add_user_lines = True
        local_conf_file.close()

        # Add enabled layers to bblayers.conf
        bblayers = " \\\n".join(["  %s" % entry for entry in self.msc_ldk_layers_for_bsp])
        new_bblayers_lines = []
        for line in (open(bblayers_conf_file_name).readlines()):
            line = line.replace("##MSC_LDK_LAYERS##", bblayers)
            new_bblayers_lines.append(line)
        bblayers_file = open(bblayers_conf_file_name, "w")
        for line in new_bblayers_lines:
            print(line, file=bblayers_file, end="")
        bblayers_file.close()

        def inform_about_file_and_backup(file_name, backup_file_name):
            if backup_file_name:
                fp_file = FilePath(file_name)
                fp_backup_file = FilePath(backup_file_name)
                if fp_file.md5_check(fp_backup_file):
                    # backup_file content and file content are identical -> restore file and get rid of the backup file
                    os.unlink(file_name)
                    os.rename(backup_file_name, file_name)
                else:
                    LOG.notice("Created backup file '%s'" % backup_file_name)
                    LOG.notice("Created '%s'" % file_name)
                    LOG.out(1, "Changes for '%s' (against '%s'):" % (file_name, backup_file_name))
                    LOG.out(1, fp_file.diff_against(fp_backup_file))
            else:
                LOG.notice("Created '%s'" % file_name)

        inform_about_file_and_backup(local_conf_file_name, local_conf_file_bak)
        inform_about_file_and_backup(bblayers_conf_file_name, bblayers_conf_file_bak)

    def create_bsp_build_dir(self, bsp, variant):
        if not os.path.isdir(self.bsp_build_root):
            os.makedirs(self.bsp_build_root)
        else:
            if not self.args.re_create_conf:
                if self.show_recreate_conf_warning:
                    LOG.error("'%s' does already exist -> Skipping .conf generation (use --re-create-conf to force .conf generation)" % self.bsp_build_root)
                return False

        self.update_bsp_conf(variant)
        self.create_bsp_info_files(bsp, variant)

        for link_src, link_dest in [(os.path.join(self.msc_ldk_scripts, "build.sh"), os.path.join(self.bsp_build_root, "build.sh")),
                                    (os.path.join(self.msc_ldk_scripts, "Makefile.bsp"), os.path.join(self.bsp_build_root, "Makefile")),
                                    (os.path.join(self.msc_ldk_scripts, "Makefile.in"), os.path.join(self.bsp_build_root, "Makefile.in"))]:
            if not os.path.islink(link_dest):
                os.symlink(link_src, link_dest)

        makefile_bsp_list = []
        for layer in self.active_layers:
            makefile_bsp_list.append(os.path.join(self.msc_ldk_scripts, "Makefile.bsp.%s.in" % layer.name))
            makefile_bsp_list.append(os.path.join(self.bsp_root, "msc-ldk-bsp-recipes.git", "Makefile.bsp.%s.in" % layer.name))
        makefile_bsp_list.append(os.path.join(self.bsp_root, "msc-ldk-bsp-recipes.git", "Makefile.bsp.in"))
        makefile_bsp_list.append(os.path.join(self.msc_ldk_root, "scripts", "Makefile.bsp.in"))
        makefile_bsp_list = [makefile_bsp for makefile_bsp in makefile_bsp_list if os.path.exists(makefile_bsp)]
        LOG.out(2, "Makefile.bsp.in candidates: %s" % ", ".join(makefile_bsp_list))
        makefile_bsp_in_file_name = os.path.join(self.bsp_build_root, "Makefile.bsp.in")
        if makefile_bsp_list and not os.path.islink(makefile_bsp_in_file_name):
            os.symlink(makefile_bsp_list[0], makefile_bsp_in_file_name)
        return True

    def setup_msc_ldk_maintainer(self):
        msc_ldk_maintainer = os.path.join(self.msc_ldk_sources, "msc-ldk-maintainer.git")
        if not os.path.exists(msc_ldk_maintainer):
            self.install_repo("msc/C984/msc-ldk-maintainer", msc_ldk_maintainer)

        for link_src, link_dest in [(os.path.join(msc_ldk_maintainer, "src", "maintainer.py"), os.path.join(self.msc_ldk_scripts, "maintainer.py"))]:
            if not os.path.islink(link_dest):
                os.symlink(link_src, link_dest)

    def read_version_layer_file_maybe(self, fill_command_line_parameters):
        if self.args.version_file:
            self.read_layer_snapshot = MscLdkSnapshot(self.msc_ldk_root, self.bsp_build_dir_name, self.bsp_build_root, self.bsp_mapping)
            self.read_layer_snapshot.read_version_layer(self.args.version_file)
            if fill_command_line_parameters:
                bsp, variant, layers = self.read_layer_snapshot.extract_bsp_info([l.name for l in self.layers])
                self.args.bsp = bsp
                if variant:
                    self.args.variant = variant
                for layer in layers:
                    if "layers_%s" % layer in self.args:
                        setattr(self.args, "layers_%s" % layer, True)
            return True
        else:
            self.read_layer_snapshot = None
        return False

    def store_default_settings(self):
        default_settings = configparser.ConfigParser()
        default_settings["general"] = {}
        default_settings["general"]["bsp"] = self.args.bsp
        default_settings["general"]["variant"] = self.args.variant
        active_layer_names = [t[0][7:] for t in self.args._get_kwargs() if t[1] and t[0].startswith("layers")]
        default_settings["general"]["layers"] = ",".join(active_layer_names)
        branch_or_tag_name = self.msc_ldk_active_tag_name or self.msc_ldk_active_branch_name
        default_settings["general"]["branch"] = branch_or_tag_name
        with open(self.default_settings_file, "w") as default_info_file:
            default_settings.write(default_info_file)

    def use_default_settings_maybe(self):
        if os.path.exists(self.default_settings_file):
            if self.args.bsp is None:
                if self.args.show_layer_info or self.args.re_create_conf or self.args.checkout_layers:
                    default_settings = configparser.ConfigParser()
                    default_settings.read(self.default_settings_file)
                    self.args.bsp = default_settings["general"]["bsp"]
                    self.args.variant = default_settings["general"]["variant"]
                    for layer_name in default_settings["general"]["layers"].split(","):
                        setattr(self.args, "layers_%s" % layer_name, True)

    def setup_ldk(self):
        bsp = self.args.bsp
        bsp_number = self.bsp_mapping.get(bsp, bsp)
        if bsp != bsp_number:
            bsp_info_string = "%s (alias for %s)" % (bsp, bsp_number)
        else:
            bsp_info_string = bsp
        active_layer_names = [t[0][7:] for t in self.args._get_kwargs() if t[1] and t[0].startswith("layers")]
        self.active_layers = [layer for layer in self.layers if layer.name in active_layer_names]
        msc_ldk_build_root = os.path.join(self.msc_ldk_root, "build")
        self.bsp_root = os.path.join(self.msc_ldk_sources, bsp_number)
        self.msc_ldk_based_on_yocto_branch = open(os.path.join(self.msc_ldk_scripts, "based_on_yocto.txt")).read().strip()
        self.git_repo_msc_ldk = GitRepository(self.msc_ldk_root)
        self.msc_ldk_active_branch_name, self.msc_ldk_active_tag_names = self.git_repo_msc_ldk.get_branch_and_tag_info()
        if self.msc_ldk_active_tag_names:
            self.msc_ldk_active_tag_name = self.msc_ldk_active_tag_names[0]
        else:
            self.msc_ldk_active_tag_name = None
        self.bsp_layer = os.path.join(self.bsp_root, "msc-ldk-bsp-recipes.git")

        if not ensure_ssh_mirror_is_known():
            return

        lib_mscboostpython_git = GitRepository(os.path.join(self.msc_ldk_scripts, "libMscBoostPython.git"))
        LOG.notice("libMscBoostPython is at <%s>" % (lib_mscboostpython_git.get_checkout_info_string()))
        git_server_info = "MSC-LDK git server: '%s'" % MSC_GIT_SERVER
        if MSC_GIT_SERVER_CACHE:
            git_server_info += ", MSC-LDK git server cache: '%s'" % MSC_GIT_SERVER_CACHE
        LOG.notice(git_server_info)
        LOG.notice("MSC-LDK root: %s" % self.msc_ldk_root)
        LOG.notice("MSC-LDK is based on Yocto branch: %s, MSC-LDK is at <%s>" % (self.msc_ldk_based_on_yocto_branch, self.git_repo_msc_ldk.get_checkout_info_string()))
        self.install_repo(os.path.join("msc", bsp_number, "msc-ldk-bsp-recipes"), self.bsp_layer)

        # self.determine_variant() needs the BSPs msc-ldk-bsp-recipes repository to detect possible candidates
        variant = self.determine_variant(self.args.variant)
        dir_elements = [e for e in [bsp, variant] if e]
        dir_elements.extend(active_layer_names)
        self.bsp_build_dir_name = "-".join(dir_elements)
        self.bsp_build_root = os.path.join(msc_ldk_build_root, self.bsp_build_dir_name)

        bsp_config_elems = []
        bsp_config_elems.append("BSP=%s" % bsp_info_string)
        if variant:
            bsp_config_elems.append("Variant=%s" % variant)
        layer_info_string = ", ".join([layer.description() for layer in self.active_layers])
        if layer_info_string:
            bsp_config_elems.append("Layers=%s" % layer_info_string)
        LOG.notice("MSC-LDK Configuration: %s" % ", ".join(bsp_config_elems))

        self.install_all_layers()
        self.create_bsp_build_dir(bsp, variant)
        if self.in_msc_network():
            self.setup_msc_ldk_maintainer()
        final_msg = "You can now cd to %s and run 'make' or './build.sh <image-name>'" % self.bsp_build_root

        if self.read_layer_snapshot:
            self.read_version_layer_file_maybe(fill_command_line_parameters=False)
            self.read_layer_snapshot.use_snapshot_file(self.args.dry_run)
            final_msg = None

        if self.inform_about_checkout_layers:
            LOG.info("Add the option --checkout-layers to checkout the required branches for all MSC-LDK layers")
        if self.did_errors_or_warnings_happen():
            LOG.error("MSC-LDK Setup failed")
            final_msg = None

        self.store_default_settings()

        layer_snapshot = MscLdkSnapshot(self.msc_ldk_root, self.bsp_build_dir_name, self.bsp_build_root, self.bsp_mapping)
        if self.args.show_layer_info:
            LOG.info("MSC-LDK Layer Info:")
            layer_snapshot.show_layer_info()

        if final_msg:
            LOG.info(final_msg)

    def _main(self):
        raise Exception("""

MSC-LDK has been moved to a new repository.
This repository will no longer be updated.
Please fetch MSC-LDK via

  git clone ssh://gitolite@msc-git02.msc-ge.com:9418/msc_ol99/msc-ldk

You can move the directories downloads/ and sstate-cache/ from this directory to the new clone
to improve build speed.

""")
        
        setup_msc_ldk = False
        setup_msc_ldk |= self.read_version_layer_file_maybe(fill_command_line_parameters=True)
        self.use_default_settings_maybe()
        if self.args.bsp:
            # BSP numbers start with max. 2 alphanumeric chars followed by numeric chars
            if self.args.bsp[:2].isalnum() and self.args.bsp[2:].isnumeric():
                # A well formed BSP number -> we can't verify whether it is available
                pass
            else:
                known_bsp_names = self.bsp_mapping.keys()
                # Check whether a known BPS from bsp-mapping.csv is given
                if self.args.bsp not in known_bsp_names:
                    LOG.error("BSP '%s' is not known - did you mean: '%s'" % (self.args.bsp, FindBestMatch(self.args.bsp, known_bsp_names)))
                    self._exit(1)
            setup_msc_ldk = True
        if setup_msc_ldk:
            self.setup_ldk()
        else:
            check_tools()
            check_git_access()
            self._print_usage_and_exit()
        if self.did_errors_or_warnings_happen():
            self._exit(1)

setup_msc_ldk_app = SetupMscLdkApplication()
setup_msc_ldk_app.run()
