# Copyright 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Arduino

Arduino Wiring-based Framework allows writing cross-platform software to
control devices attached to a wide range of Arduino boards to create all
kinds of creative coding, interactive objects, spaces or physical experiences.

http://arduino.cc/en/Reference/HomePage
"""

import subprocess
import importlib.util
import json
import semantic_version
import sys
from os.path import join

from SCons.Script import COMMAND_LINE_TARGETS, DefaultEnvironment, SConscript
from platformio.package.version import pepver_to_semver

env = DefaultEnvironment()
DEPS = {
    "wheel": ">=0.35.1",
    "zopfli": ">=0.2.2"
}


if "nobuild" not in COMMAND_LINE_TARGETS:
    SConscript(
        join(DefaultEnvironment().PioPlatform().get_package_dir(
            "framework-arduinoespressif8266"), "tools", "platformio-build.py"))

def install_python_deps():
    def _get_installed_pip_packages():
        result = {}
        packages = {}
        pip_output = subprocess.check_output(
            [
                env.subst("$PYTHONEXE"),
                "-m",
                "pip",
                "list",
                "--format=json",
                "--disable-pip-version-check",
            ]
        )
        try:
            packages = json.loads(pip_output)
        except:
            print("Warning! Couldn't extract the list of installed Python packages.")
            return {}
        for p in packages:
            result[p["name"]] = pepver_to_semver(p["version"])

        return result

    installed_packages = _get_installed_pip_packages()
    packages_to_install = []
    for package, spec in DEPS.items():
        if package not in installed_packages:
            packages_to_install.append(package)
        else:
            version_spec = semantic_version.Spec(spec)
            if not version_spec.match(installed_packages[package]):
                packages_to_install.append(package)

    if packages_to_install:
        env.Execute(
            env.VerboseAction(
                (
                    '"$PYTHONEXE" -m pip install -U '
                    + " ".join(
                        [
                            '"%s%s"' % (p, DEPS[p])
                            for p in packages_to_install
                        ]
                    )
                ),
                "Installing Python dependencies",
            )
        )


if sys.prefix != sys.base_prefix:
    # This means we are in a venv and can assume pip to be available and being able to install packages
    install_python_deps()
else:
    # Very likely this is a system python installation, there is no guarantee that pip is available
    # and even if it is, it's unlikely that installing packages with it is the correct thing to do.
    # Instead we check if our dependencies are already available through importlib and print an error
    # message telling the user to use the system package manager to install (or run the build in a
    # venv) them in case they are not
    missing_deps = []
    for dep in DEPS.keys():
        if not importlib.util.find_spec(dep):
            missing_deps.append(dep)
    if len(missing_deps) > 0:
        print(f"""
MISSING BUILD DEPENDENCIES!
Please ensure the following dependencies are available in this python environment:
{missing_deps}

Alternatively run this build inside a python venv. Dependencies can then be auto-installed.
        """)
        sys.exit(1)
