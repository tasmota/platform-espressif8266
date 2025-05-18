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

import os
import json
import subprocess
import sys
import shutil
from os.path import join

from platformio.public import PlatformBase, to_unix_path
from platformio.proc import get_pythonexe_path
from platformio.project.config import ProjectConfig
from platformio.package.manager.tool import ToolPackageManager


IS_WINDOWS = sys.platform.startswith("win")
# Set Platformio env var to use windows_amd64 for all windows architectures
# only windows_amd64 native espressif toolchains are available
# needs platformio/pioarduino core >= 6.1.17
if IS_WINDOWS:
    os.environ["PLATFORMIO_SYSTEM_TYPE"] = "windows_amd64"

python_exe = get_pythonexe_path()
pm = ToolPackageManager()

class Espressif8266Platform(PlatformBase):
    def configure_default_packages(self, variables, targets):
        if not variables.get("board"):
            return super().configure_default_packages(variables, targets)

        frameworks = variables.get("pioframework", [])

        def install_tool(TOOL, retry_count=0):
            self.packages[TOOL]["optional"] = False
            TOOL_PATH = os.path.join(ProjectConfig.get_instance().get("platformio", "packages_dir"), TOOL)
            TOOL_PACKAGE_PATH = os.path.join(TOOL_PATH, "package.json")
            TOOLS_PATH_DEFAULT = os.path.join(os.path.expanduser("~"), ".platformio")
            IDF_TOOLS = os.path.join(ProjectConfig.get_instance().get("platformio", "packages_dir"), "tl-install", "tools", "idf_tools.py")
            TOOLS_JSON_PATH = os.path.join(TOOL_PATH, "tools.json")
            TOOLS_PIO_PATH = os.path.join(TOOL_PATH, ".piopm")
            IDF_TOOLS_CMD = (
                python_exe,
                IDF_TOOLS,
                "--quiet",
                "--non-interactive",
                "--tools-json",
                TOOLS_JSON_PATH,
                "install"
            )

            tl_flag = bool(os.path.exists(IDF_TOOLS))
            json_flag = bool(os.path.exists(TOOLS_JSON_PATH))
            pio_flag = bool(os.path.exists(TOOLS_PIO_PATH))
            if tl_flag and json_flag:
                rc = subprocess.run(IDF_TOOLS_CMD).returncode
                if rc != 0:
                    sys.stderr.write("Error: Couldn't execute 'idf_tools.py install'\n")
                else:
                    tl_path = "file://" + join(TOOLS_PATH_DEFAULT, "tools", TOOL)
                    try:
                        shutil.copyfile(TOOL_PACKAGE_PATH, join(TOOLS_PATH_DEFAULT, "tools", TOOL, "package.json"))
                    except FileNotFoundError as e:
                        sys.stderr.write(f"Error copying tool package file: {e}\n")
                    if os.path.exists(TOOL_PATH) and os.path.isdir(TOOL_PATH):
                        try:
                            shutil.rmtree(TOOL_PATH)
                        except Exception as e:
                            print(f"Error while removing the tool folder: {e}")
                    pm.install(tl_path)
            # tool is already installed, just activate it
            if tl_flag and pio_flag and not json_flag:
                with open(TOOL_PACKAGE_PATH, "r") as file:
                    package_data = json.load(file)
                # check installed tool version against listed in platforms.json
                if "package-version" in self.packages[TOOL] \
                   and "version" in package_data \
                   and self.packages[TOOL]["package-version"] == package_data["version"]:
                    self.packages[TOOL]["version"] = TOOL_PATH
                    self.packages[TOOL]["optional"] = False
                elif "package-version" not in self.packages[TOOL]:
                    # No version check needed, just use the installed tool
                    self.packages[TOOL]["version"] = TOOL_PATH
                    self.packages[TOOL]["optional"] = False
                elif "version" not in package_data:
                    print(f"Warning: Cannot determine installed version for {TOOL}. Reinstalling...")
                else:  # Installed version does not match required version, deinstall existing and install needed
                    if os.path.exists(TOOL_PATH) and os.path.isdir(TOOL_PATH):
                        try:
                            shutil.rmtree(TOOL_PATH)
                        except Exception as e:
                            print(f"Error while removing the tool folder: {e}")
                    if retry_count >= 3:  # Limit to 3 retries
                        print(f"Failed to install {TOOL} after multiple attempts. Please check your network connection and try again manually.")
                        return
                    print(f"Wrong version for {TOOL}. Installing needed version...")
                    install_tool(TOOL, retry_count + 1)

            return

        # Installer only needed for setup, deactivate when installed
        if bool(os.path.exists(os.path.join(ProjectConfig.get_instance().get("platformio", "packages_dir"), "tl-install", "tools", "idf_tools.py"))):
            self.packages["tl-install"]["optional"] = True

        if "arduino" in frameworks:
            self.packages["framework-arduinoespressif8266"]["optional"] = False
            install_tool("toolchain-xtensa")


        CHECK_PACKAGES = [
            "tool-cppcheck",
            "tool-clangtidy",
            "tool-pvs-studio"
        ]
        # Install check tool listed in pio entry "check_tool"
        if variables.get("check_tool") is not None:
            for package in CHECK_PACKAGES:
                for check_tool in variables.get("check_tool", ""):
                    if check_tool in package:
                        install_tool(package)

        if "buildfs" or "uploadfs" or "downloadfs" in targets:
            filesystem = variables.get("board_build.filesystem", "littlefs")
            if filesystem == "littlefs":
                install_tool("tool-mklittlefs")
            elif filesystem == "spiffs":
                install_tool("tool-mkspiffs")

        return super().configure_default_packages(variables, targets)

    def get_boards(self, id_=None):
        result = super().get_boards(id_)
        if not result:
            return result
        if id_:
            return self._add_upload_protocols(result)
        else:
            for key, value in result.items():
                result[key] = self._add_upload_protocols(result[key])
        return result

    def _add_upload_protocols(self, board):
        if not board.get("upload.protocols", []):
            board.manifest['upload']['protocols'] = ["esptool", "espota"]
        if not board.get("upload.protocol", ""):
            board.manifest['upload']['protocol'] = "esptool"
        return board
