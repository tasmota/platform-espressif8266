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
import json
import semantic_version
from os.path import join

from SCons.Script import COMMAND_LINE_TARGETS, DefaultEnvironment, SConscript
from platformio.package.version import pepver_to_semver

env = DefaultEnvironment()

if "nobuild" not in COMMAND_LINE_TARGETS:
    SConscript(
        join(DefaultEnvironment().PioPlatform().get_package_dir(
            "framework-arduinoespressif8266"), "tools", "platformio-build.py"))

def install_python_deps():
    def _get_installed_packages():
        result = {}
        packages = {}
        
        # First try uv, fallback to pip if uv is not available
        try:
            uv_output = subprocess.check_output(
                [
                    "uv",
                    "pip",
                    "list",
                    "--format=json"
                ]
            )
            packages = json.loads(uv_output)
            use_uv = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to pip if uv is not available
            try:
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
                packages = json.loads(pip_output)
                use_uv = False
            except:
                print("Warning! Couldn't extract the list of installed Python packages.")
                return {}, False
        except:
            print("Warning! Couldn't extract the list of installed Python packages.")
            return {}, False
            
        for p in packages:
            result[p["name"]] = pepver_to_semver(p["version"])

        return result, use_uv

    deps = {
        "wheel": ">=0.35.1",
        "zopfli": ">=0.2.2"
    }

    installed_packages, use_uv = _get_installed_packages()
    packages_to_install = []
    for package, spec in deps.items():
        if package not in installed_packages:
            packages_to_install.append(package)
        else:
            version_spec = semantic_version.Spec(spec)
            if not version_spec.match(installed_packages[package]):
                packages_to_install.append(package)

    if packages_to_install:
        if use_uv:
            # Use uv for package installation
            env.Execute(
                env.VerboseAction(
                    (
                        'uv pip install '
                        + " ".join(
                            [
                                '"%s%s"' % (p, deps[p])
                                for p in packages_to_install
                            ]
                        )
                    ),
                    "Installing Python dependencies with uv",
                )
            )
        else:
            # Fallback to pip
            env.Execute(
                env.VerboseAction(
                    (
                        '"$PYTHONEXE" -m pip install -U '
                        + " ".join(
                            [
                                '"%s%s"' % (p, deps[p])
                                for p in packages_to_install
                            ]
                        )
                    ),
                    "Installing Python dependencies with pip",
                )
            )

install_python_deps()
