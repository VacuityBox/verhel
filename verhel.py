# MIT License
#
# Copyright (c) 2021 VacuityBox
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# SPDX-License-Identifier: MIT

import argparse
import collections
import datetime
import io
import json
import os
import pathlib
import shlex
import shutil
import string
import subprocess
import sys
import textwrap
import time

# ============================================================================ #
# Frontends definition buffer.
# ============================================================================ #

# $$_BUILDER_FRONTENDS_DESC_START_HERE_$$ #
FRONTENDS_DESC = R'''
{
    "git": {
        "version": "1.0.0",
        "exe": "git",
        "get.repo": {
            "cmd": "git rev-parse --git-dir",
            "ret_codes": [0]
        },
        "get.commit_hash": {
            "cmd": "git rev-parse HEAD",
            "ret_codes": [0]
        },
        "get.short_hash":  {
            "cmd": "git rev-parse --short HEAD",
            "ret_codes": [0]
        },
        "get.tag":  {
            "cmd": "git describe --tags --abbrev=0 --exact-match",
            "ret_codes": [0, 128]
        },
        "get.branch": {
            "cmd": "git rev-parse --abbrev-ref HEAD",
            "ret_codes": [0]
        },
        "get.commit_count": {
            "cmd": "git rev-list --count HEAD",
            "ret_codes": [0]
        }
    }
}
'''
# $$_BUILDER_FRONTENDS_DESC_END_HERE_$$ #

# ============================================================================ #
# Backends definition buffer.
# ============================================================================ #

# $$_BUILDER_BACKENDS_DESC_START_HERE_$$ #
BACKENDS_DESC = R'''
{
    "cpp": {
        "version": "1.0.0",
        "source.begin":   "#pragma once\n\nnamespace verhel {\n\n",
        "source.comment": "//",
        "source.end":     "\n} // namespace verhel\n",
        "format.bool":    "    inline constexpr auto {0} = {1};\n",
        "format.number":  "    inline constexpr auto {0} = {1};\n",
        "format.string":  "    inline constexpr auto {0} = \"{1!u}\";\n",
        "format.var":     "{0!u}",
        "var_map": [
            { "version.major":       "VERSION_MAJOR      " },
            { "version.minor":       "VERSION_MINOR      " },
            { "version.patch":       "VERSION_PATCH      " },
            { "version.pre_release": "VERSION_PRE_RELEASE" },
            { "version.string":      "VERSION_STRING     " },
            { "project.name":        "PROJECT_NAME       " },
            { "project.author":      "PROJECT_AUTHOR     " },
            { "project.license":     "PROJECT_LICENSE    " },
            { "project.copyright":   "PROJECT_COPYRIGHT  " },
            { "project.description": "PROJECT_DESCRIPTION" },
            { "project.directory":   "PROJECT_DIRECTORY  " },
            { "project.path":        "PROJECT_PATH       " },
            { "build.date":          "BUILD_DATE         " },
            { "build.time":          "BUILD_TIME         " },
            { "vcs.name":            "VCS_NAME           " },
            { "vcs.commit_hash":     "VCS_COMMIT_HASH    " },
            { "vcs.short_hash":      "VCS_SHORT_HASH     " },
            { "vcs.tag":             "VCS_TAG            " },
            { "vcs.branch":          "VCS_BRANCH         " },
            { "vcs.commit_count":    "VCS_COMMIT_COUNT   " }
        ]
    }
}
'''
# $$_BUILDER_BACKENDS_DESC_END_HERE_$$ #

# ============================================================================ #
# Exit codes
# ============================================================================ #
class ExitCodes:
    SUCCESS                       = 0
    FAILED_TO_LOAD_PROJECTS       = 1
    FAILED_TO_SAVE_PROJECTS       = 2
    FAILED_TO_LOAD_FRONTENDS      = 3
    FAILED_TO_LOAD_BACKENDS       = 4
    PROJECT_DOESNT_EXISTS         = 5
    PROJECT_ALREADY_EXISTS        = 6
    PROJECT_VALIDATION_FAILED     = 7
    FRONTEND_DOESNT_EXISTS        = 8
    BACKEND_DOESNT_EXISTS         = 9
    FAILED_TO_ENTER_PROJECT_DIR   = 10
    VERSION_CONTROL_NOT_INSTALLED = 11
    REPO_DOESNT_EXISTS            = 12
    INVALID_KEY                   = 13
    INVALID_VALUE                 = 14
    VERSION_IS_NULL               = 15

# ============================================================================ #
# Logger
# ============================================================================ #
USE_COLOR_OUTPUT = True

class LogType:
    DEBUG   = 0
    INFO    = 1
    SUCCESS = 2
    WARNING = 3
    ERROR   = 4
    FATAL   = 5

    @staticmethod
    def to_str(log_type):
        if log_type == LogType.DEBUG:
            return "DEBUG"
        elif log_type == LogType.INFO:
            return "INFO"
        elif log_type == LogType.SUCCESS:
            return "SUCCESS"
        elif log_type == LogType.WARNING:
            return "WARNING"
        elif log_type == LogType.ERROR:
            return "ERROR"
        elif log_type == LogType.FATAL:
            return "FATAL"
        else:
            return ""

class LogBackend:
    def __init__(self):
        self.log_level = LogType.INFO

    def log(self, log_type, time, message):
        raise NotImplementedError()

    def set_log_level(self, log_level):
        self.log_level = log_level

class LogBackendConsole(LogBackend):
    def log(self, log_type, time, message):
        if self.log_level > log_type:
            return

        color = ""
        reset_color = ""

        global USE_COLOR_OUTPUT
        if USE_COLOR_OUTPUT:
            color = "\033[39m"
            reset_color = "\033[0m"
            if log_type == LogType.DEBUG:
                color = "\033[34m"
            elif log_type == LogType.INFO:
                color = "\033[39m"
            elif log_type == LogType.SUCCESS:
                color = "\033[32m"
            elif log_type == LogType.WARNING:
                color = "\033[33m"
            elif log_type == LogType.ERROR:
                color = "\033[31m"
            elif log_type == LogType.FATAL:
                color = "\033[101m"

        print("{}[{:8.3f}] {}{}".format(color, time, message, reset_color))

class LogBackendFile(LogBackend):
    def __init__(self, file_name):
        super().__init__()
        self.file = None

        try:
            self.file = open(file_name, "w")
        except:
            pass
        else:
            #self.file.write("---- log started ----\n")
            pass

    def __del__(self):
        if self.file is not None:
            #self.file.write("---- log closed ----\n")
            self.file.close()

    def log(self, log_type, time, message):
        if self.log_level > log_type:
            return

        if self.file is not None:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
            time = datetime.datetime.now().strftime("%H:%M:%S")
            log_type_str = LogType.to_str(log_type)
            self.file.write("{} {} [{:7}] {}\n".format(date, time, log_type_str, message))
        
class Log:
    __backends   = []
    __start_time = time.time()

    @staticmethod
    def add_backend(backend: LogBackend):
        Log.__backends.append(backend)

    @staticmethod
    def __log(log_type, message):
        from_start = time.time() - Log.__start_time
        for backends in Log.__backends:
            backends.log(log_type, from_start, message)

    @staticmethod
    def debug(message):
        Log.__log(LogType.DEBUG, message)

    @staticmethod
    def info(message):
        Log.__log(LogType.INFO, message)

    @staticmethod
    def success(message):
        Log.__log(LogType.SUCCESS, message)

    @staticmethod
    def warn(message):
        Log.__log(LogType.WARNING, message)

    @staticmethod
    def error(message):
        Log.__log(LogType.ERROR, message)

    @staticmethod
    def fatal(message):
        Log.__log(LogType.FATAL, message)

# ============================================================================ #
# VerHel class
# ============================================================================ #
class VerHelFormatter(string.Formatter):
    def convert_field(self, value, conversion):
        if conversion == "u":
            return str(value).upper()
        elif conversion == "l":
            return str(value).lower()
        
        return super().convert_field(value, conversion)

class VerHelError(Exception):
    def __init__(self, error_code):
        self.error_code = error_code

class VerHel:
    def __init__(self):
        self.projects             = {}
        self.frontends            = {}
        self.backends             = {}
        self.script_directory     = os.path.realpath(__file__)
        self.command_timeout      = 2 # in seconds
        self.fatal_if_bk_not_impl = False
        self.emit_default_values  = False
        self.DESC_TYPE            = dict # collections.OrderedDict
        self.GLOBAL_DESC_NAME     = "_Global"
        self.PROJECTS_DEFAULT_FILE_NAME  = "verhel.json"
        self.FRONTENDS_DEFAULT_FILE_NAME = "frontends.json"
        self.BACKENDS_DEFAULT_FILE_NAME  = "backends.json"

        self.log_bk_console = LogBackendConsole()
        self.log_bk_file = LogBackendFile("verhel.log")
        Log.add_backend(self.log_bk_console)
        Log.add_backend(self.log_bk_file)

    def load_from_buffer(self, buffer):
        Log.info("loading json from buffer")

        try:
            root = json.loads(buffer, object_pairs_hook=self.DESC_TYPE)
        except json.decoder.JSONDecodeError as e:
            Log.error("failed to decode json: {}".format(e))
            raise
        else:
            Log.success("loaded json from buffer succesfully")
            return root

    def load_from_file(self, file_name):
        Log.info("loading file '{}'".format(file_name))

        try:
            with open(file_name, "r", encoding="utf-8") as f:
                buffer = f.read()
        except IOError as e:
            Log.error("failed to read '{}'".format(file_name))
            Log.error("{}".format(e))
            raise
        else:
            Log.success("read file '{}'".format(file_name))
            return self.load_from_buffer(buffer)

    def load_frontends_from_buffer(self, buffer):
        try:
            root = self.load_from_buffer(buffer)
        except:
            return False
        else:
            self.frontends = root
            return True

    def load_frontends_from_file(self, file_name):
        try:
            root = self.load_from_file(file_name)
        except:
            return False
        else:
            self.frontends = root
            return True

    def load_backends_from_buffer(self, buffer):
        try:
            root = self.load_from_buffer(buffer)
        except:
            return False
        else:
            self.backends = root
            return True

    def load_backends_from_file(self, file_name):
        try:
            root = self.load_from_file(file_name)
        except:
            return False
        else:
            self.backends = root
            return True

    def load_frontends(self, file_name=None):
        if file_name is None:
            load_fn = self.load_frontends_from_buffer
            load_arg = FRONTENDS_DESC
            load_from = "internal description"
        else:
            load_fn = self.load_frontends_from_file
            load_arg = file_name
            load_from = file_name
        
        Log.info("loading frontends from '{}'".format(load_from))

        if not load_fn(load_arg):
            Log.fatal("failed to load frontends")
            raise VerHelError(ExitCodes.FAILED_TO_LOAD_FRONTENDS)
        else:
            Log.success("loaded frontends ({})".format(len(self.frontends)))
            Log.debug("loaded frontends: {}".format(list(self.frontends.keys())))

    def load_backends(self, file_name=None):
        if file_name is None:
            load_fn = self.load_backends_from_buffer
            load_arg = BACKENDS_DESC
            load_from = "internal description"
        else:
            load_fn = self.load_backends_from_file
            load_arg = file_name
            load_from = file_name
        
        Log.info("loading backends from '{}'".format(load_from))

        if not load_fn(load_arg):
            Log.fatal("failed to load backends")
            raise VerHelError(ExitCodes.FAILED_TO_LOAD_BACKENDS)
        else:
            Log.success("loaded backends ({})".format(len(self.backends)))
            Log.debug("loaded backends: {}".format(list(self.backends.keys())))

    def load_projects(self, file_name=None):
        if file_name is None:
            file_name = self.PROJECTS_DEFAULT_FILE_NAME
        
        Log.info("loading projects description from '{}'".format(file_name))

        try:
            root = self.load_from_file(file_name)
        except:
            Log.fatal("failed to load projects")
            raise VerHelError(ExitCodes.FAILED_TO_LOAD_PROJECTS)
        else:
            self.projects = root
            Log.success("loaded projects ({})".format(len(self.projects)))
            Log.debug("loaded projects: {}".format(list(self.projects.keys())))

    def save_projects(self, file_name=None):
        if file_name is None:
            file_name = self.PROJECTS_DEFAULT_FILE_NAME
        
        Log.info("saving projects to '{}'".format(file_name))

        try:
            with open(file_name, "w") as f:
                f.write(json.dumps(self.projects, indent=4))
        except IOError as e:
            Log.error("failed to write '{}'".format(file_name))
            Log.error("{}".format(e))
            raise VerHelError(ExitCodes.FAILED_TO_SAVE_PROJECTS)
        else:
            Log.success("wrote project file '{}'".format(file_name))
        
    def empty_project(self):
        return {
            "backends": [],
            "exclude": [],
            "frontend": None,
            "license.spdx": None,
            "license.file": None,
            "project.name": None,
            "project.author": None,
            "project.copyright": None,
            "project.description": None,
            "project.directory": None,
            "version.major": None,
            "version.minor": None,
            "version.patch": None,
            "version.pre_release": None
        }

    def default_project(self):
        return {
            "backends": [],
            "exclude": [],
            "frontend": "",
            "license.spdx": "",
            "license.file": "",
            "project.name": "",
            "project.author": "",
            "project.copyright": "",
            "project.description": "",
            "project.directory": "",
            "version.major": 0,
            "version.minor": 1,
            "version.patch": 0,
            "version.pre_release": ""
        }        

    def validate_project(self, project_name):
        def check(desc, key, expected_type):
            # Null is allowed.
            ty = type(desc.get(key))
            if ty is not expected_type and ty is not type(None):
                raise TypeError(
                    "invalid type for key '{}' expected '{}' found '{}'".format(
                        key,
                        expected_type.__name__,
                        ty.__name__
                    )
                )
        
        Log.info("validating project '{}'".format(project_name))
        desc = self.projects.get(project_name)
        try:
            if type(desc) is not self.DESC_TYPE:
                raise TypeError("project description is not an object")

            # Check version.
            check(desc, "version.major", int)
            check(desc, "version.minor", int)
            check(desc, "version.patch", int)
            check(desc, "version.pre_release", str)

            # Check backends.
            backends_list = desc.get("backends")
            if backends_list is not None:
                check(desc, "backends", list)
                for bk in backends_list:
                    index = backends_list.index(bk)
                    if type(bk) is not self.DESC_TYPE:
                        raise TypeError("backend[{}] is not an object".format(index))
                    if len(bk.items()) > 1:
                        raise Exception("backend[{}] only one item in object is allowed".format(index))

                    for name, output in bk.items():
                        check(bk, name, str)

                        # Backend output can't be null.
                        if output is None:
                            raise TypeError("backend '{}' output is null".format(name))

                # Check for duplicates.
                for bk in backends_list:
                    index = backends_list.index(bk)
                    name = list(bk.keys())[0]
                    output = bk.get(name)
                    for i in range(len(backends_list)):
                        if i == index:
                            continue

                        # Duplicated name.
                        if backends_list[i].get(name) is not None:
                            raise Exception("duplicated backend '{}'".format(name))

                        # Duplicated output.
                        other_name = list(backends_list[i].keys())[0]
                        other_output = backends_list[i].get(other_name)
                        
                        if other_output == output:
                            raise Exception("backends output '{}' and '{}' override eachother"
                                .format(name, other_name)
                                )

            # Check forntend.
            check(desc, "frontend", str)

            # Check rest.
            check(desc, "license.spdx", str)
            check(desc, "license.file", str)
            check(desc, "project.author", str)
            check(desc, "project.copyright", str)
            check(desc, "project.company", str)
            check(desc, "project.description", str)
            check(desc, "project.directory", str)
            check(desc, "project.name", str)

            check(desc, "exclude", list)
        except TypeError as e:
            Log.error("{}".format(e))
            Log.fatal("failed to validate project '{}'".format(project_name))
            raise VerHelError(ExitCodes.PROJECT_VALIDATION_FAILED)
        except Exception as e:
            Log.error("{}".format(e))
            Log.fatal("failed to validate project '{}'".format(project_name))
            raise VerHelError(ExitCodes.PROJECT_VALIDATION_FAILED)
        else:
            # Check for dangling properties.
            empty = self.empty_project()
            for key, _ in desc.items():
                if not key in empty:
                    Log.warn("dangling property '{}'".format(key))

            Log.success("project '{}' validated".format(project_name))

    def validate_version(self, desc):
        if desc.get("version.major") is None:
            Log.fatal("version.major is null")
            raise VerHelError(ExitCodes.VERSION_IS_NULL)
        if desc.get("version.minor") is None:
            Log.fatal("version.minor is null")
            raise VerHelError(ExitCodes.VERSION_IS_NULL)
        if desc.get("version.patch") is None:
            Log.fatal("version.patch is null")
            raise VerHelError(ExitCodes.VERSION_IS_NULL)

    def use_global_desc_values(self, desc, glob_name = None):
        if glob_name is None:
            glob_name = self.GLOBAL_DESC_NAME

        glob_desc = self.projects.get(glob_name)
        if glob_desc is None:
            return

        Log.info("using global description '{}'".format(glob_name))

        for key, value in desc.items():
            if value is None:
                gvalue = glob_desc.get(key)
                desc[key] = gvalue
                Log.info("using global value for '{}' new value: '{}'".format(key, gvalue))

        Log.info("finished using global description")

    def check_if_project_exists(self, project_name):
        Log.info("checking if project '{}' exists".format(project_name))

        desc = self.projects.get(project_name)
        if desc is None:
            Log.fatal("project '{}' doesn't exists".format(project_name))
            raise VerHelError(ExitCodes.PROJECT_DOESNT_EXISTS)

        Log.info("project description '{}' found".format(project_name))
        return desc
    
    def check_if_frontend_exists(self, frontend_name):
        Log.info("checking if frontend '{}' is implemented".format(frontend_name))
        
        frontend = self.frontends.get(frontend_name)
        if frontend is None:
            Log.fatal("frontend '{}' doesn't exists".format(frontend_name))
            raise VerHelError(ExitCodes.FRONTEND_DOESNT_EXISTS)

        Log.success("fronted '{}' found".format(frontend_name))
        return frontend

    def check_if_backends_exists(self, backends_list):
        bklstr = [name for bk in backends_list for name, _ in bk.items()]
        Log.info("checking if backends '{}' are implemented".format(bklstr))
        
        found = 0
        for bk in backends_list:
            for name, _ in bk.items():
                if self.backends.get(name) is None:
                    err_msg = "backend '{}' not found".format(name)
                    if self.fatal_if_bk_not_impl:
                        Log.fatal(err_msg)
                        raise VerHelError(ExitCodes.BACKEND_DOESNT_EXISTS)
                    else:
                        Log.error(err_msg)

                    found = found + 1
                else:
                    Log.success("backend '{}' found".format(name))

        if found == len(backends_list):
            Log.success("all backends used by project are implemented")
        else:
            Log.warn("not all backends used by project are implemented")

    def cd_into_project_directory(self, desc):
        Log.info("building project path")
        project_directory = desc.get("project.directory")

        # If project.directory is null, then current working directory
        # is consitered project root.
        full_path = pathlib.Path(pathlib.Path.cwd())
        if project_directory is not None:
            # If path is absolute than use it as directory.
            # Otherwise concat with current working directory.
            if pathlib.Path.is_absolute(project_directory):
                full_path = pathlib.Path(project_directory)
            else:
                full_path = full_path / pathlib.Path(project_directory)
        
        # If projet directory don't exists, create.
        if not full_path.exists():
            Log.info("project directory don't exist, creating")
            pathlib.Path(full_path).mkdir(parents=True, exist_ok=True) 

        Log.info("changing directory to '{}'".format(full_path))
        try:
            os.chdir(full_path)
        except OSError as e:
            Log.fatal("failed to change directory")
            Log.error("{}".format(e))
            raise VerHelError(ExitCodes.FAILED_TO_ENTER_PROJECT_DIR)
        else:
            Log.success("successfuly cd into project directory")

    def run_cmd(self, cmd):
        args = shlex.split(cmd)
        Log.debug("args: {}".format(args))

        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                timeout=self.command_timeout,
                encoding="utf-8"
                )
        except TimeoutError:
            Log.error("command failed")
            raise Exception("Command '{}' timed out".format(cmd))
        except:
            Log.error("command failed")
            raise Exception("Unknown error when executing '{}'".format(cmd))

        Log.debug("    return code: {}".format(proc.returncode))
        Log.debug("    output: {}".format(proc.stdout.strip()))

        return (proc.returncode, proc.stdout)

    def check_if_vcs_is_installed(self, frontend):
        exe_name = frontend.get("exe")
        Log.info("checking if vcs executable '{}' is found".format(exe_name))
        
        if not shutil.which(exe_name):
            Log.fatal("vcs is not installed or not in path")
            raise VerHelError(ExitCodes.VERSION_CONTROL_NOT_INSTALLED)
        else:
            Log.success("vcs executable '{}' found".format(exe_name))

    def check_if_project_repo_exists(self, frontend):
        Log.info("checking if repo exists")

        get_repo = frontend.get("get.repo")
        try:
            ret, _ = self.run_cmd(get_repo.get("cmd"))
        except Exception as e:
            Log.error(e)
            raise VerHelError(ExitCodes.REPO_DOESNT_EXISTS)
        else: 
            if ret not in get_repo.get("ret_codes"):
                Log.fatal("version control repository doesn't exists")
                raise VerHelError(ExitCodes.REPO_DOESNT_EXISTS)
            else:
                Log.success("version control repository found")

    def get_vcs_info(self, frontend, frontend_name):
        def run_wrapper(cmd_name, out_type = str):
            cmd_obj = frontend.get(cmd_name)
            cmd = cmd_obj.get("cmd")
            ret_codes = cmd_obj.get("ret_codes")
            if cmd is None:
                Log.error("command '{}' is null in frontend '{}'".format(cmd_name, frontend_name))
                return None

            try:
                Log.info("command '{}' ('{}')".format(cmd_name, cmd))
                ret, out = self.run_cmd(cmd)
            except Exception as e:
                Log.error(e)
                return None
            else:
                if ret in ret_codes:
                    Log.success("command finished")
                    return out_type(out.strip())
                else:
                    Log.error("command failed")
                    return None

        Log.info("geting info from version control")

        info = {}
        info["name"]         = frontend_name
        info["commit_hash"]  = run_wrapper("get.commit_hash")
        info["short_hash"]   = run_wrapper("get.short_hash")
        info["tag"]          = run_wrapper("get.tag")
        info["branch"]       = run_wrapper("get.branch")
        info["commit_count"] = run_wrapper("get.commit_count", int)

        Log.info("finished getting vcs info")

        return info

    def get_build_info(self):
        return {
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.datetime.now().strftime("%H:%M:%S")
            }

    def get_default_info(self):
        return {
            "version.major":       0,
            "version.minor":       1,
            "version.patch":       0,
            "version.pre_release": "",
            "version.string":      "",
            "vcs.name":            "",
            "vcs.commit_hash":     "",
            "vcs.short_hash":      "",
            "vcs.tag":             "",
            "vcs.branch":          "",
            "vcs.commit_count":    0,
            "project.name":        "",
            "project.copyright":   "",
            "project.description": "",
            "project.directory":   "",
            "build.date":          "",
            "build.time":          ""
            }

    def check_if_name_is_valid(self, name):
        if name.startswith("backends."):
            bk_name = name[len("backends."):]
            if len(bk_name) == 0:
                Log.fatal("backend name can't be empty")
                raise VerHelError(ExitCodes.INVALID_KEY)
            else:
                return bk_name
        else:
            empty = self.empty_project()
            if name not in empty:
                Log.fatal("'{}' is not a valid name".format(name))
                raise VerHelError(ExitCodes.INVALID_KEY)
            else:
                return name

    def cook_info(self, project_name, desc, build_info, vcs_info):
        def dget(key, default_value = None):
            value = desc.get(key)
            if value is None:
                if default_value is None:
                    return self.default_project().get(key)
                else:
                    return default_value
            else:
                return value

        Log.info("cooking info for backend")
        info = {}

        # Cook version.
        info["version.major"]       = desc.get("version.major") 
        info["version.minor"]       = desc.get("version.minor")
        info["version.patch"]       = desc.get("version.patch")
        info["version.pre_release"] = desc.get("version.pre_release")

        if desc.get("version.pre_release") is not None:
            info["version.string"] = "{}.{}.{}-{}".format(
                desc.get("version.major"),
                desc.get("version.minor"),
                desc.get("version.patch"),
                desc.get("version.pre_release")
            )
        else:
            info["version.string"] = "{}.{}.{}".format(
                desc.get("version.major"),
                desc.get("version.minor"),
                desc.get("version.patch")
            )
            info["version.pre_release"] = ""

        # Cook rest.
        info["project.name"]        = dget("project.name", project_name)
        info["project.author"]      = dget("project.author")
        info["project.license"]     = dget("license.spdx")
        info["project.copyright"]   = dget("project.copyright")
        info["project.company"]     = dget("project.company")
        info["project.description"] = dget("project.description")
        info["project.directory"]   = dget("project.directory")
        #info["project.directory"]   = get_desc_value(desc, "directory", glob_desc)
        info["project.path"]        = str(pathlib.Path.cwd().as_posix())
        info["license.spdx"]        = desc.get("license.spdx")
        info["license.file"]        = desc.get("license.file")

        # Cook build info.
        info["build.date"] = build_info["date"]
        info["build.time"] = build_info["time"]

        # Cook vcs info.
        info["vcs.name"]         = dget("frontend")
        info["vcs.commit_hash"]  = vcs_info.get("commit_hash")
        info["vcs.short_hash"]   = vcs_info.get("short_hash")
        info["vcs.branch"]       = vcs_info.get("branch")
        info["vcs.tag"]          = vcs_info.get("tag")
        info["vcs.commit_count"] = vcs_info.get("commit_count")

        Log.success("cooking finished")
        Log.debug("cooked info: {}".format(info))

        return info

    def backend_generate(self, backend, cooked_info, license_text, excluded_vars=[]):
        fmtr = VerHelFormatter()
        ss = io.StringIO()
        format_bool    = backend.get("format.bool")
        format_number  = backend.get("format.number")
        format_string  = backend.get("format.string")        
        format_var     = backend.get("format.var")        
        source_begin   = backend.get("source.begin") 
        source_comment = backend.get("source.comment") 
        source_end     = backend.get("source.end") 

        # Write beginning.
        if license_text is not None:
            license_commented = ""
            for line in license_text.rstrip().splitlines():
                license_commented += ("{} {}\n".format(source_comment, line))
            ss.write(license_commented)
        if cooked_info["license.spdx"] is not None: 
            if license_text is not None:
                ss.write("{}\n".format(source_comment))
            ss.write("{} SPDX-License-Identifier: {}\n".format(source_comment, cooked_info["license.spdx"]))
        
        ss.write(source_begin)

        # Write variables
        for var in backend.get("var_map"):
            var_name, emit_name = next(iter(var.items()))

            # Check if value is excluded.
            if var_name in excluded_vars:
                continue

            # Emit value.
            value = cooked_info[var_name]            
            if value is not None:
                _ty = type(value)
                if _ty is int or _ty is float:
                    ss.write(fmtr.format(format_number, emit_name, value))
                elif _ty is str:
                    #ss.write(format_string.format(emit_name, value))
                    ss.write(fmtr.format(format_string, emit_name, value))
                else:
                    Log.warn("don't know how to write type '{}, writing as string'".format(_ty.__name__))
                    ss.write(fmtr.format(format_string, emit_name, value))
            else:
                Log.warn("emiting value '{}' is null".format(var_name))

        # Write ending.
        ss.write(source_end)
        ss.write("\n{0} generated using verhel.py {0}\n".format(source_comment))

        return ss.getvalue()

    def verhel_generate_sources(self, project_name, desc, vcs_info):
        # Get build info.
        build_info = self.get_build_info()

        # Read license.
        license_text = None
        if desc["license.file"] is not None:
            try:
                with open(desc["license.file"], encoding="utf-8") as f:
                    license_buffer = f.read()
            except IOError as e:
                Log.error("failed to load license file '{}'".format(desc["license.file"]))
                pass
            else:
                license_text = license_buffer

        # Cook info.
        cooked_info = self.cook_info(project_name, desc, build_info, vcs_info)
        exclude = desc.get("exclude")
        if exclude is None:
            exclude = []

        num_success = 0

        Log.info("running generate for project '{}'...".format(project_name))

        for backend_desc in desc.get("backends"):
            for bk_name, bk_output in backend_desc.items():
                backend = self.backends.get(bk_name)
                if backend is not None:
                    Log.info("    generating source using '{}' backend".format(bk_name))
                    
                    buffer = self.backend_generate(backend, cooked_info, license_text, exclude)

                    # Build output path.
                    output_path = pathlib.Path(bk_output)
                    pathlib.Path(output_path.parent).mkdir(parents=True, exist_ok=True) 
                    
                    try:
                        with open(output_path, "w", encoding="utf-8") as f:
                            bytes_write = f.write(buffer)
                    except IOError as e:
                        Log.error("    can't open or write '{}'".format(output_path))
                        Log.error("    {}".format(e))
                    else:
                        Log.success("    successfully wrote '{}' ({} b)".format(output_path, bytes_write))
                        num_success += 1
                else:
                    Log.error("    backend '{}' is not implemented".format(bk_name))

        return num_success

    def process_arguments(self, args, cmd):
        # Color output.
        global USE_COLOR_OUTPUT
        USE_COLOR_OUTPUT = args.color_output

        # Verbosity level.
        if args.quiet == True:
            self.log_bk_console.set_log_level(LogType.FATAL + 1)
        else:
            if args.verbose == 0:
                lvl = LogType.FATAL
            elif args.verbose == 1:
                lvl = LogType.SUCCESS
            elif args.verbose == 2:
                lvl = LogType.INFO
            else:
                lvl = LogType.DEBUG
            
            self.log_bk_console.set_log_level(lvl)
            self.log_bk_file.set_log_level(lvl)

        Log.debug("command line arguments:")

        # Print debug info.
        Log.debug("quiet='{}'".format(args.quiet))
        Log.debug("verbose='{}'".format(args.verbose))
        Log.debug("color_output='{}'".format(args.color_output))
        if cmd in ["init", "generate", "delete", "info", "get", "set", "validate", "list_projects"]:
            Log.debug("project_file='{}'".format(args.projects_file))
            Log.debug("project_name='{}'".format(args.project))
        
        if cmd in ["generate"]:
            self.emit_default_values = args.emit_default
            self.fatal_if_bk_not_impl = args.fatal_if_backend_not_impl

            Log.debug("glob_desc_name='{}'".format(args.global_desc_name))
            Log.debug("emit_default='{}'".format(args.emit_default))
            Log.debug("fatal_if_backend_not_impl='{}'".format(args.fatal_if_backend_not_impl))

        if cmd in ["get", "set"]:
            Log.debug("property_name='{}'".format(args.property_name))

        if cmd in ["generate", "list_frontends"]:
            Log.debug("frontends_file='{}'".format(args.frontends_file))

        if cmd in ["generate", "list_backends"]:
            Log.debug("backends_file='{}'".format(args.backends_file))

    def init(self, args):
        # Command line arguments.
        self.process_arguments(args, "init")
        project_name = args.project
        projects_file = args.projects_file
        
        Log.info("running init command")

        # If project description file exists, try load the project.
        if pathlib.Path(projects_file).exists():
            try:
                self.load_projects(projects_file)
            except VerHelError as e:
                return e.error_code

            # Check name collision.
            for name, _ in self.projects.items():
                if name == project_name:
                    Log.fatal("project '{}' already exists".format(project_name))
                    return ExitCodes.PROJECT_ALREADY_EXISTS

        # Add new project.
        new_desc = self.empty_project()
        self.projects[project_name] = new_desc
        
        # Update projects file.
        try:
            self.save_projects(projects_file)
        except VerHelError as e:
            return e.error_code

        Log.success("successfully added new project '{}'".format(project_name))

        return ExitCodes.SUCCESS

    def generate(self, args):
        # Command line arguments.
        self.process_arguments(args, "generate")
        project_name = args.project
        projects_file = args.projects_file
        frontends_file = args.frontends_file
        backends_file = args.backends_file
        glob_desc_name = args.global_desc_name

        Log.info("running generate command")
        
        # Load project and validate.
        try:
            self.load_projects(projects_file)
            desc = self.check_if_project_exists(project_name)
            self.validate_project(project_name)

            if glob_desc_name is not None:
                self.validate_project(glob_desc_name)
                self.use_global_desc_values(desc, glob_desc_name)

            self.validate_version(desc)
        except VerHelError as e:
            return e.error_code

        # Load frontends if project uses one.
        vcs = desc.get("frontend")
        if vcs is not None:
            try:
                self.load_frontends(frontends_file)
                frontend = self.check_if_frontend_exists(vcs)
                self.check_if_vcs_is_installed(frontend)
            except VerHelError as e:
                return e.error_code

        # Load backends if project uses one.
        backends_list = desc.get("backends")
        if backends_list is not None and len(backends_list) > 0:
            try:
                self.load_backends(backends_file)
                self.check_if_backends_exists(backends_list)
            except VerHelError as e:
                return e.error_code
        else:
            Log.warn("no backends found in project '{}'".format(project_name))
            Log.info("nothing to do, terminating")
            return ExitCodes.SUCCESS

        # Change current directory to project root directory.
        # So all the commands are exucuted there.
        try:
            self.cd_into_project_directory(desc)
        except VerHelError as e:
            return e.error_code

        # Get information from Version Control System.
        vcs_info = {}
        if vcs is not None:
            try:
                self.check_if_project_repo_exists(frontend)
            except:
                return ExitCodes.REPO_DOESNT_EXISTS
            else:
                vcs_info = self.get_vcs_info(frontend, vcs)

        # Run Generate.
        num_success = self.verhel_generate_sources(project_name, desc, vcs_info)

        fmt = "successfully generated for {}/{} backends"
        if num_success == len(backends_list):
            Log.success(fmt.format(num_success, len(backends_list)))
        else:
            Log.warn(fmt.format(num_success, len(backends_list)))

        Log.info("generate command finished")
        return ExitCodes.SUCCESS

    def delete(self, args):
        # Command line arguments.
        self.process_arguments(args, "delete")
        project_name = args.project
        projects_file = args.projects_file
        
        Log.info("running delete command")

        # Load project.
        try:
            self.load_projects(projects_file)
            _ = self.check_if_project_exists(project_name)
        except VerHelError as e:
            return e.error_code

        # Delete project.
        self.projects.pop(project_name)

        # Update projects file.
        try:
            self.save_projects(projects_file)
        except VerHelError as e:
            return e.error_code

        Log.success("successfully deleted project '{}'".format(project_name))

        Log.info("delete command finished")
        return ExitCodes.SUCCESS

    def info(self, args):
        # Command line arguments.
        self.process_arguments(args, "info")
        project_name = args.project
        projects_file = args.projects_file

        Log.info("running info command")

        # Load project.
        try:
            self.load_projects(projects_file)
            desc = self.check_if_project_exists(project_name)
        except VerHelError as e:
            return e.error_code

        # Pretty print project description.
        info = json.dumps(desc, indent=4)
        print(info)
        Log.debug(info)

        Log.success("info command finished")
        return ExitCodes.SUCCESS

    def validate(self, args):
        # Command line arguments.
        self.process_arguments(args, "validate")
        project_name = args.project
        projects_file = args.projects_file

        Log.info("running validate command")

        # Load project.
        try:
            self.load_projects(projects_file)
            _ = self.check_if_project_exists(project_name)
            self.validate_project(project_name)
        except VerHelError as e:
            return e.error_code

        # Pretty print project description.
        if not args.quiet:
            print("OK")

        Log.success("validate command finished")
        return ExitCodes.SUCCESS

    def get(self, args):
        # Command line arguments.
        self.process_arguments(args, "get")
        project_name = args.project
        projects_file = args.projects_file
        property_name = args.property_name

        Log.info("running get command")
        
        # Load project and validate.
        try:
            key = self.check_if_name_is_valid(property_name)
            self.load_projects(projects_file)
            desc = self.check_if_project_exists(project_name)            
        except VerHelError as e:
            return e.error_code

        # Check if key exists, if so then print the value.
        # Backends are special case.
        value = None
        if property_name.startswith("backends."):
            # Check if backend exists.        
            index = 0
            backends = desc.get("backends")
            for bk in backends:
                v = bk.get(key)
                if v is not None:
                    break
                index = index + 1

            # Get value.
            if index == len(backends):
                Log.fatal("backend '{}' doesn't exists".format(key))
                return ExitCodes.BACKEND_DOESNT_EXISTS
            else:                
                value = backends[index][key]
        else:
            value = desc[key]

        print(value)
        Log.success("successfully get value for property {} = '{}'".format(property_name, value))

        Log.info("get command finished")
        return ExitCodes.SUCCESS

    def set(self, args):
        # Command line arguments.
        self.process_arguments(args, "set")
        project_name = args.project
        projects_file = args.projects_file
        property_name = args.property_name
        new_value = args.new_value

        Log.info("running set command")
        
        # Load project and validate.
        try:
            key = self.check_if_name_is_valid(property_name)
            self.load_projects(projects_file)
            desc = self.check_if_project_exists(project_name)
        except VerHelError as e:
            return e.error_code

        # Check if key exists and validate type.
        # Backends are special case.
        old_value = None
        if key.startswith("backends."):
            # Check if backend exists.        
            index = 0
            backends = desc.get("backends")
            for bk in backends:
                v = bk.get(key)
                if v is not None:
                    break
                index = index + 1

            # Add new value or else update.
            # If new value is null that mean to remove.
            if index == len(backends):
                if new_value != "null":
                    backends.append({key: str(new_value)})
            else:
                if new_value != "null":
                    old_value = backends[index][key]
                    backends[index][key] = str(new_value)
                else:
                    backends.pop(index)
        else:    
            default = self.default_project()
            old_value = desc.get(key)
            if type(default[key]) is int:
                try:
                    converted = int(new_value)
                except ValueError as e:
                    Log.fatal(e)
                    Log.fatal("invalid new value '{}' for property '{}'".format(new_value, key))
                    return ExitCodes.INVALID_VALUE
                else:
                    new_value = converted

            # Add/Update value.
            desc[key] = new_value

        # Update projects file.
        try:
            self.save_projects(projects_file)
        except VerHelError as e:
            return e.error_code

        if old_value is None:
            Log.success("successfully set value for '{}', new value '{}'".format(key, new_value))
        else:
            Log.success("successfully set value for '{}', old '{}' new '{}'".format(key, old_value, new_value))

        Log.info("set command finished")
        return ExitCodes.SUCCESS

    def list_projects(self, args):
        # Command line arguments.
        self.process_arguments(args, "list_projects")
        projects_file = args.projects_file

        Log.info("running list projects command")

        # Load backends.
        try:
            self.load_projects(projects_file)
        except VerHelError as e:
            return e.error_code

        # Pretty print project description.   
        print(list(self.projects.keys()))

        Log.success("list projects command finished")
        return ExitCodes.SUCCESS  
        
    def list_frontends(self, args):
        # Command line arguments.
        self.process_arguments(args, "list_frontends")
        frontends_file = args.frontends_file

        Log.info("running list frontends command")

        # Load backends.
        try:
            self.load_frontends(frontends_file)
        except VerHelError as e:
            return e.error_code

        # Pretty print project description.
        print(list(self.frontends.keys()))

        Log.success("list frontends command finished")
        return ExitCodes.SUCCESS  
        
    def list_backends(self, args):
        # Command line arguments.
        self.process_arguments(args, "list_backends")
        backends_file = args.backends_file

        Log.info("running list backends command")

        # Load backends.
        try:
            self.load_backends(backends_file)
        except VerHelError as e:
            return e.error_code

        # Print available backends.
        print(list(self.backends.keys()))

        Log.success("list backends command finished")
        return ExitCodes.SUCCESS

    def update(self, args):
        # Command line arguments.
        self.process_arguments(args, "update")
        backends_file = args.backends_file

        Log.info("running update command")

        

        Log.success("update command finished")
        return ExitCodes.SUCCESS

# ============================================================================ #
# Main function
# ============================================================================ #
def main():    
    verhel = VerHel()

    # Parse command line arguments
    parser = argparse.ArgumentParser()
    gp_verbosity = parser.add_mutually_exclusive_group()
    gp_verbosity.add_argument("--quiet", action="store_true", help="no console output")
    gp_verbosity.add_argument("--verbose", type=int, choices=[0, 1, 2, 3], default=0,
                              help="show more info about what is happening")
    parser.add_argument("--color-output", action="store_true", help="color the console output")
    subparsers = parser.add_subparsers(title="Commands")

    sp_init = subparsers.add_parser("init")
    sp_init.add_argument("project", help="name of project to init")
    sp_init.add_argument("--projects-file", type=str, help="path to custom projects description file")
    sp_init.set_defaults(func=verhel.init)

    sp_generate = subparsers.add_parser(
        "generate",
        formatter_class = argparse.RawDescriptionHelpFormatter,
        description = textwrap.dedent("""
            This will generate source code for specific project.
            Run before building task.
            """
            )
        )
    sp_generate.add_argument("project", help="name of project to update")
    sp_generate.add_argument("--projects-file", type=str, help="path to custom projects description file")
    sp_generate.add_argument("--frontends-file", type=str, help="path to custom fronteds description file")
    sp_generate.add_argument("--backends-file", type=str, help="path to custom backends description file")
    sp_generate.add_argument("--global-desc-name", type=str, help="name of global description project")
    sp_generate.add_argument("--emit-default", action="store_true", 
                             help="emit default value if description property is null")
    sp_generate.add_argument("--fatal-if-backend-not-impl", action="store_false", 
                             help=textwrap.dedent("""
                                stop execution if backend not implemented
                                (by default it will generate source with
                                backends that are implemented) 
                                """
                                )
                             )
    sp_generate.set_defaults(func=verhel.generate)

    sp_delete = subparsers.add_parser("delete")
    sp_delete.add_argument("project", help="name of project to delete")
    sp_delete.add_argument("--projects-file", type=str, help="path to custom projects description file")
    sp_delete.set_defaults(func=verhel.delete)

    sp_info = subparsers.add_parser("info")
    sp_info.add_argument("project", help="name of project to display info")
    sp_info.add_argument("--projects-file", type=str, help="path to custom projects description file")
    sp_info.set_defaults(func=verhel.info)

    sp_validate = subparsers.add_parser("validate")
    sp_validate.add_argument("project", help="name of project to display validate")
    sp_validate.add_argument("--projects-file", type=str, help="path to custom projects description file")
    sp_validate.set_defaults(func=verhel.validate)

    sp_get = subparsers.add_parser("get")
    sp_get.add_argument("project", help="name of project to get value from")
    sp_get.add_argument("property_name", help="name of property to get value")
    sp_get.add_argument("--projects-file", type=str, help="path to custom projects description file")
    sp_get.set_defaults(func=verhel.get)

    sp_set = subparsers.add_parser("set")
    sp_set.add_argument("project", help="name of project to set value to")
    sp_set.add_argument("property_name", help="name of property to get value")
    sp_set.add_argument("new_value", help="new value to be set")
    sp_set.add_argument("--projects-file", type=str, help="path to custom projects description file")
    sp_set.set_defaults(func=verhel.set)

    sp_list_proj = subparsers.add_parser("list_projects")
    sp_list_proj.add_argument("--projects-file", type=str, help="path to custom projects description file")
    sp_list_proj.set_defaults(func=verhel.list_projects)

    sp_list_front = subparsers.add_parser("list_frontends")
    sp_list_front.add_argument("--frontends-file", type=str, help="path to custom fronteds description file")
    sp_list_front.set_defaults(func=verhel.list_frontends)

    sp_list_back = subparsers.add_parser("list_backends")
    sp_list_back.add_argument("--backends-file", type=str, help="path to custom backends description file")
    sp_list_back.set_defaults(func=verhel.list_backends)

    args = parser.parse_args()
    ret = args.func(args)

    sys.exit(ret)

if __name__ == "__main__":
    main()
