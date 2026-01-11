#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2019 Riverbank Computing Limited
# SPDX-FileCopyrightText: 2021 L. E. Segovia <amy@amyspark.me>
# SPDX-License-Identifier: GPL-2.0-or-later

from sipbuild.abstract_project import AbstractProject
from sipbuild.exceptions import handle_exception
from sipbuild.module import get_source_version_range

def main():
    """ Generate the project bindings from the command line. """

    try:
        project = AbstractProject.bootstrap(
            'build', "Generate the project bindings.")
        target_abi = getattr(project, "target_abi", None)
        if (isinstance(target_abi, tuple) and len(target_abi) == 2 and
                target_abi[1] is None):
            # Use the oldest available minor for this major to avoid
            # None comparisons and keep ABI consistent with sip.h.
            major = target_abi[0]
            try:
                oldest_minor, _ = get_source_version_range(major)
            except Exception:
                oldest_minor = 0
            project.target_abi = (major, oldest_minor)
        project.builder._generate_bindings()
        project.progress("The project bindings are ready for build.")
    except Exception as e:
        handle_exception(e)

    return 0

if __name__ == "__main__":
    main()
