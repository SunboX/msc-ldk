#! /usr/bin/python3

import os
import sys

print("""
MSC-LDK has been moved. This repository will no longer be updated.
Please fetch MSC-LDK from the new repository:

  git clone ssh://gitolite@msc-git02.msc-ge.com:9418/msc_ol99/msc-ldk

You can move the directories downloads/ and sstate-cache/ from this directory to the new cloned MSC-LDK to improve build speed.
""")

sys.exit(1)

# Use MscBoost from this libMscBoostPython checkout
sys.path.insert(0, "{0}/libMscBoostPython.git/src".format(os.path.dirname(__file__)))

from MscBoost.Application import Application
from MscBoost.Git import GitRepository, MscGitRepository, GitException
from MscBoost.Logging import Log
from MscBoost.MscProject import MscProject

class UpdateApplication(Application):
    """Updates MSC-LDK and all it's layers"""

    def __init__(self):
        super(self.__class__,self).__init__(
            "update.py",
            "Updates MSC-LDK and all it's layers.")
        self.msc_ldk_root = os.path.realpath(os.path.join(os.path.realpath(__file__), "..", ".."))

    def _main(self):
        """Updates MSC-LDK and the layers."""
        # Update MSC-LDK itself
        self._update_repository_at_path(self.msc_ldk_root)

        # Update all the layers
        layer_paths = self._get_repositories_paths(
            os.path.join(self.msc_ldk_root, "sources"),
            1)

        # scripts is not included. A tagged version of libMscBoostPython is explicitly checked out by setup when needed

        for path in layer_paths:
            self._update_repository_at_path(path)
            
    ## @param path From where to start searching
    ## @param levels_remaining If <=0, no further subdirectories will be processed.
    ## @return List of paths which are git repositories
    def _get_repositories_paths(self, path, levels_remaining):
        """Recursively returns a list of paths containing GIT repositories."""
        paths = []

        for entry in os.listdir(path):
            entry_path = os.path.join(path, entry)
            if not os.path.isdir(entry_path):
                # Only directories can contain repositories.
                continue

            if entry_path.endswith(".git"):
                paths.append(entry_path)
            else:
                if levels_remaining > 0:
                    paths.extend(
                        self._get_repositories_paths(entry_path, levels_remaining - 1))

        return paths

    ## @param path The local path to the git repository
    def _update_repository_at_path(self, path):
        """Performs a git update at path."""
        Log().out(0, "Updating {}".format(path))

        repo = MscGitRepository(path)
        head_commit = repo.head.commit
        repo.update()
        updated_commit = repo.head.commit

        if updated_commit != head_commit:
            Log().info(" Updated {} -> {}".format(
                head_commit,
                updated_commit))

    def _get_usage_examples(self):
        """Returns the example help text for --help."""
        return """
  update.py
     Performs a git pull on MSC-LDK and all it's layers.
"""

    def _print_version(self):
        """Prints the application version. As this script is not part of a cmake environment, we have to provide our own implementation."""
        # This is not a full MscProject (missing COPYING etc.),
        # but is sufficient for getting the version

        proj = MscProject(self.msc_ldk_root)
        Log().out(0, "Version: {}".format(str(proj.version)))

    def _print_copyright(self):
        """Prints the copyright. As this script is not part of a cmake environment, we have to provide our own implementation."""
        with open(os.path.join(self.msc_ldk_root, "COPYING_linked")) as f:
            Log().out(0, f.read())
    
app = UpdateApplication()
sys.exit(app.run())
    
